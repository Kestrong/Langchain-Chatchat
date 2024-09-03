import base64
import json
from contextvars import ContextVar

from configs import MOCK_TOKEN_INFO, MOCK_TOKEN_INFO_ENABLED

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
