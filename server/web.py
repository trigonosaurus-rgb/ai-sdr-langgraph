"""Serving the built frontend from the API server, and security headers on every response."""

import os

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Everything the page needs comes from this origin; the theme script is a file, not inline.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "media-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
SECURITY_HEADERS = [
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
]
HSTS = (b"strict-transport-security", b"max-age=31536000")


class SecurityHeaders:
    """Adds security headers without buffering the body, so SSE streams pass through untouched.
    HSTS only over HTTPS: behind a TLS-terminating proxy the scheme comes from proxy headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = SECURITY_HEADERS + ([HSTS] if scope.get("scheme") == "https" else [])

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [h for h in extra if h[0] not in present]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class FrontendFiles(StaticFiles):
    """The Vite build. Files under assets/ have content hashes in their names and are cached for good;
    everything else (index.html, examples) is revalidated, so a deploy is picked up on the next load."""

    def file_response(self, full_path, stat_result, scope, status_code=200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        hashed = self.get_path(scope).startswith("assets" + os.sep)
        response.headers["cache-control"] = "public, max-age=31536000, immutable" if hashed else "no-cache"
        return response
