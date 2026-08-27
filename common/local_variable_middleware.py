import datetime
import hashlib
import hmac
import json
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from configs import CIAM_TOKEN_COOKIE_NAME, MOCK_TOKEN_INFO_ENABLED, logger
from server.db.repository import get_app_by_api_key_from_db
from server.memory.token_info_memory import set_token_context, i18n_context, get_token_info


def signature(params, secret, algorithm='HmacSHA256'):
    """
    生成签名字符串
    :param params: 字典，如 {'a': '1', 'b': '2'}
    :param secret: 密钥字符串
    :param algorithm: 算法，目前支持 'HmacSHA256'，其他则使用 SHA256 拼接
    :return: 小写十六进制签名字符串
    """
    # 提取非 None 的值，并按 key 排序
    keys = sorted(k for k in params.keys() if params[k] is not None)
    # 拼接所有 value
    data = ''.join(str(params[k]) for k in keys)

    if algorithm == 'SHA256':
        # 普通 SHA256：data + secret
        raw = data + secret
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
    else:
        # 使用 HMAC-SHA256
        mac = hmac.new(
            secret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        )
        return mac.hexdigest()


def check_app_code(app_code):
    app = get_app_by_api_key_from_db(api_key=app_code)
    if app is None:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "msg": "Invalid App Code"}
        )
    if app.get('expired_time') and app.get('expired_time') <= datetime.datetime.now():
        return JSONResponse(
            status_code=401,
            content={"code": 401, "msg": "App expired"}
        )
    return app


def is_internal_request(request: Request) -> bool:
    # 优先从 X-Forwarded-For 获取真实 IP（兼容 Nginx 等反向代理）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host

    # 校验 IP 是否在白名单中
    if client_ip in ("127.0.0.1", "::1"):
        return True

    return False


class LocaleVariableMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app_code = request.headers.get('X-App-Code')
        if app_code:
            app = check_app_code(app_code)
            if isinstance(app, JSONResponse):
                return app
            user_id = request.headers.get('X-User-Id')
            timestamp = request.headers.get('X-Timestamp')
            nonce = request.headers.get('X-Nonce')
            algorithm = request.headers.get('X-Algorithm')
            sign = request.headers.get('X-Sign')
            secret_key = app.get('secret_key')
            if secret_key:
                # 参考OSS签名机制 15分钟窗口避免时钟不准 所有接口均幂等无需防止重放
                signature_timeout_minutes = int(os.environ.get('SIGNATURE_TIMEOUT_MINUTES', 15))
                server_now = datetime.datetime.now()
                client_time = datetime.datetime.fromtimestamp(int(timestamp) / 1000)
                time_diff = abs(server_now - client_time)
                if time_diff > datetime.timedelta(minutes=signature_timeout_minutes):
                    return JSONResponse(
                        status_code=401,
                        content={"code": 401, "msg": "Timestamp expired"}
                    )
                gen_sign = signature(
                    params={'app_code': app_code, 'user_id': user_id, 'timestamp': timestamp, 'nonce': nonce},
                    secret=secret_key,
                    algorithm=algorithm)
                if sign != gen_sign:
                    return JSONResponse(
                        status_code=401,
                        content={"code": 401, "msg": "Signature verification failed"}
                    )
            set_token_context(
                {'token_type': 'sign',
                 'token': json.dumps({'appCode': app_code, 'userId': user_id, 'timestamp': timestamp, 'nonce': nonce,
                                      'algorithm': algorithm, 'sign': sign, 'tenantId': None})})
            logger.info(f"Operator by sign user: {user_id}, app code: {app_code}")
        else:
            token = request.headers.get("Authorization")
            if token is None or token.strip() == '':
                token = request.cookies.get(CIAM_TOKEN_COOKIE_NAME)
            if token:
                if "/openapi/" in request.url.path:
                    token_parts = token.split("Bearer ")
                    app_code = token_parts[1] if len(token_parts) > 1 else token
                    app = check_app_code(app_code)
                    if isinstance(app, JSONResponse):
                        return app
                    set_token_context(
                        {'token_type': 'api_key',
                         'token': json.dumps(
                             {'appCode': app_code, 'userId': f"app-{app.get('id')}", 'tenantId': None})})
                    logger.info(f"Operator by app code: {app_code}")
                else:
                    set_token_context({'token_type': 'jwt', 'token': token})
                    logger.info(f"Operator by user: {get_token_info().get('userId')}")
            else:
                if MOCK_TOKEN_INFO_ENABLED and not "/openapi/" in request.url.path:
                    logger.info(f"Operator by mock user: {get_token_info().get('userId')}")
                elif is_internal_request(request):
                    set_token_context(
                        {'token_type': 'mock',
                         'token': json.dumps({'appCode': 'flm-chat', 'userId': f"INTERNAL", 'tenantId': None})})
                    logger.info(f"Operator by flm-chat self internal")
                else:
                    return JSONResponse(
                        status_code=401,
                        content={"code": 401, "msg": "Missing Jwt token or signature"}
                    )

        locale = request.cookies.get('LOCALE')
        if locale:
            i18n_context.set(locale)
        response = await call_next(request)
        return response


if __name__ == '__main__':
    print(signature(
        params={'app_code': "test", 'user_id': 1, 'timestamp': '12345', 'nonce': "12345"},
        secret='123456'))
