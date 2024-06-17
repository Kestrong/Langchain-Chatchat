import base64
import json
from contextvars import ContextVar

# 创建一个线程本地变量
token_context = ContextVar[str]('X_Token', default=None)


def get_token() -> str:
    return token_context.get()


def get_token_info() -> dict:
    token = get_token()
    if token:
        part = str(token).split(".")[1]
        part = part + '=' * ((4 - (len(part) % 4)) % 4)
        return json.loads(base64.b64decode(part).decode('utf-8'))
    return {}


def set_token(token):
    token_context.set(token)
