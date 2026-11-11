"""Security headers on every response."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Only this site's own scripts and styles; server icons come from Discord's CDN. No inline code,
# no plugins, and the site can't be framed by another site (clickjacking).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' https://cdn.discordapp.com data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

HEADERS = {
    "content-security-policy": CSP,
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "cross-origin-opener-policy": "same-origin",
}

# The interactive docs load Swagger UI / ReDoc from a CDN and use inline scripts, so they get no CSP.
DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, enable_api_docs: bool = False):
        self.app = app
        self.enable_api_docs = enable_api_docs

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        skip_csp = self.enable_api_docs and scope["path"].startswith(DOCS_PATHS)
        is_https = scope.get("scheme") == "https"

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])]
                present = {k.decode().lower() for k, _ in headers}
                for name, value in HEADERS.items():
                    if name == "content-security-policy" and skip_csp:
                        continue
                    if name not in present:
                        headers.append((name.encode(), value.encode()))
                if is_https and "strict-transport-security" not in present:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
