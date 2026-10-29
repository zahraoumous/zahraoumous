"""Bound multipart intake before spooling untrusted uploads to disk."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = 101 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    await JSONResponse({"detail": "Invalid content length"}, status_code=400)(
                        scope, receive, send
                    )
                    return
                if length < 0 or length > self.max_bytes:
                    await JSONResponse(
                        {"detail": "Request exceeds the 100 MiB batch limit"}, status_code=413
                    )(scope, receive, send)
                    return
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    raise HTTPException(413, "Request exceeds the 100 MiB batch limit")
            return message

        await self.app(scope, bounded_receive, send)
