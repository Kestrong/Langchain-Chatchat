from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware, GZipResponder
from starlette.requests import Request
from starlette.types import ASGIApp, Scope, Receive, Send


class CustomGZipMiddleware(GZipMiddleware):
    def __init__(
            self, app: ASGIApp, minimum_size: int = 500, compresslevel: int = 9, exclude_paths=None
    ) -> None:
        super().__init__(app, minimum_size, compresslevel)
        self.exclude_paths = exclude_paths or []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", "") and "application/json" in headers.get("Accept", ""):
                request = Request(scope=scope, receive=receive, send=send)
                if not any(request.url.path.endswith(suffix) for suffix in self.exclude_paths):
                    responder = GZipResponder(
                        self.app, self.minimum_size, compresslevel=self.compresslevel
                    )
                    await responder(scope, receive, send)
                    return
        await self.app(scope, receive, send)
