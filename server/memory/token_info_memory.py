import base64
import json
from contextvars import ContextVar
from typing import Optional

from configs import MOCK_TOKEN_INFO, MOCK_TOKEN_INFO_ENABLED, DEFAULT_LOCALE

# 创建一个线程本地变量
TOKEN_CONTEXT = ContextVar[dict]('X_Token', default={})


def get_token() -> Optional[str]:
    return TOKEN_CONTEXT.get().get('token')


def get_token_headers() -> dict:
    headers = {}
    token_type = TOKEN_CONTEXT.get().get('token_type', 'jwt')
    if token_type == 'jwt':
        headers['Authorization'] = get_token()
    return headers


def get_token_info() -> dict:
    token = get_token()
    if token:
        # 认证类型 jwt/sign/api_key/mock
        token_type = TOKEN_CONTEXT.get().get('token_type', 'jwt')
        if token_type in ['sign', 'mock', 'api_key']:
            token_info = json.loads(token)
            token_info['token_type'] = token_type
            return token_info
        parts = str(token).split(".")
        if len(parts) < 3:
            return {}
        part = parts[1]
        part = part + '=' * ((4 - (len(part) % 4)) % 4)
        token_info = json.loads(base64.b64decode(part, b'-_').decode('utf-8'))
        token_info['token'] = token
        token_info['token_type'] = token_type
        if 'userId' not in token_info and 'user_id' in token_info:
            token_info['userId'] = token_info.pop('user_id')
        return token_info
    if MOCK_TOKEN_INFO_ENABLED:
        token_info = MOCK_TOKEN_INFO
        token_info['token_type'] = 'mock'
    else:
        token_info = {}
    return token_info


def set_token_context(token_context: dict):
    TOKEN_CONTEXT.set(token_context)


i18n_context = ContextVar[str]('i18n', default=DEFAULT_LOCALE)


def is_english() -> bool:
    i18n = i18n_context.get()
    if i18n is None:
        return False
    return i18n.__contains__('en') or i18n.__contains__('us')
