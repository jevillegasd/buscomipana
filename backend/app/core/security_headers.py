from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

settings = get_settings()


class SecurityHeadersMiddleware:
    """Baseline defense-in-depth response headers, applied to every response.

    The CSP/HSTS pair is skipped in local dev: Swagger/ReDoc load their JS/CSS
    from a CDN by default, which a strict CSP would break, and there's no TLS
    to make HSTS meaningful locally anyway. In every other environment, docs
    are disabled outright (see main.py) rather than CSP-exempted, so the
    strict policy never needs a carve-out.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._headers())
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _headers(self) -> list[tuple[bytes, bytes]]:
        pairs = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            # The frontend needs geolocation for the ping location-capture
            # flow; every other sensitive permission is denied outright.
            (b"permissions-policy", b"geolocation=(self), camera=(), microphone=()"),
        ]
        if not settings.is_local:
            csp = (
                b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                b"img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
                b"frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
            pairs.append((b"content-security-policy", csp))
            if settings.cookie_secure:
                # Only advertised once the app is actually confirmed to be
                # served over HTTPS (cookie_secure implies that) -- HSTS on a
                # plain-HTTP deployment would just break it for every visitor.
                pairs.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
        return pairs
