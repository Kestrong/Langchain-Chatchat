import base64
import json
from contextvars import ContextVar

from configs import MOCK_TOKEN_INFO, MOCK_TOKEN_INFO_ENABLED, DEFAULT_LOCALE

# 创建一个线程本地变量
token_context = ContextVar[str]('X_Token', default=None)


def get_token() -> str:
    return token_context.get()


def get_token_info() -> dict:
    token = get_token()
    if token:
        parts = str(token).split(".")
        if len(parts) < 3:
            return {}
        part = parts[1]
        part = part + '=' * ((4 - (len(part) % 4)) % 4)
        return json.loads(base64.b64decode(part, b'-_').decode('utf-8'))
    return MOCK_TOKEN_INFO or {} if MOCK_TOKEN_INFO_ENABLED else {}


def set_token(token):
    token_context.set(token)


i18n_context = ContextVar[str]('i18n', default=DEFAULT_LOCALE)


def is_english() -> bool:
    i18n = i18n_context.get()
    if i18n is None:
        return False
    return i18n.__contains__('en') or i18n.__contains__('us')
