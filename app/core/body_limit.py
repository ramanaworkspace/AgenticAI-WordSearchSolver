"""Bound request bodies before JSON or multipart parsing."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class BodyLimitMiddleware:
    """Reject oversized solve requests before multipart files are spooled."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in {
            "/api/v1/solve",
            "/api/v1/solve/image",
        }:
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/api/v1/solve/image":
            try:
                limit = get_settings().image_max_bytes + 65536
            except ValueError:
                response = JSONResponse(
                    {"detail": "Image extraction settings are invalid; contact the administrator."},
                    status_code=503,
                )
                await response(scope, receive, send)
                return
        else:
            limit = 262144

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                response = JSONResponse(
                    {"detail": "Request body exceeds the configured processing limit."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)
