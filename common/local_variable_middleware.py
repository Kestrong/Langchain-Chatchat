from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from configs import CIAM_TOKEN_COOKIE_NAME
from server.memory.token_info_memory import set_token, i18n_context


class LocaleVariableMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if token is None or token.strip() == '':
            token = request.cookies.get(CIAM_TOKEN_COOKIE_NAME)
        set_token(token)
        locale = request.cookies.get('LOCALE')
        if locale:
            i18n_context.set(locale)
        response = await call_next(request)
        return response
