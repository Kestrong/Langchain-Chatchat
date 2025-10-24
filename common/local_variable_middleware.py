import datetime
import hashlib
import hmac
import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from configs import CIAM_TOKEN_COOKIE_NAME, MOCK_TOKEN_INFO_ENABLED
from server.db.repository import get_app_by_api_key_from_db
from server.memory.token_info_memory import set_token_context, i18n_context


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


class LocaleVariableMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if token is None or token.strip() == '':
            token = request.cookies.get(CIAM_TOKEN_COOKIE_NAME)
        if token:
            set_token_context({'token_type': 'jwt', 'token': token})
        else:
            app_code = request.headers.get('X-App-Code')
            if app_code:
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
                user_id = request.headers.get('X-UserId')
                timestamp = request.headers.get('X-Timestamp')
                nonce = request.headers.get('X-Nonce')
                algorithm = request.headers.get('X-Algorithm')
                sign = request.headers.get('X-Sign')
                if algorithm != 'Basic':
                    gen_sign = signature(
                        params={'app_code': app_code, 'user_id': user_id, 'timestamp': timestamp, 'nonce': nonce},
                        secret=app.get('secret_key'),
                        algorithm=algorithm)
                    if sign != gen_sign:
                        return JSONResponse(
                            status_code=401,
                            content={"code": 401, "msg": "Signature verification failed"}
                        )
                set_token_context(
                    {'token_type': 'sign',
                     'token': json.dumps({'appCode': app_code, 'userId': user_id, 'tenantId': None})})
            else:
                if not MOCK_TOKEN_INFO_ENABLED:
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
