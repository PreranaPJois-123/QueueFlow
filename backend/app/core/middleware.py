"""Cross-cutting HTTP protections: CSRF, origin checks, body limits, headers."""
import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# These endpoints do not act on an existing session (they create one or use a
# reset token), so they are exempt from the CSRF check; the Origin allowlist
# still applies to them.
CSRF_EXEMPT = {"/api/auth/login", "/api/auth/register", "/api/auth/password-reset/request",
               "/api/auth/password-reset/confirm"}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.MAX_REQUEST_BYTES:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
            origin = request.headers.get("origin")
            if origin and origin not in settings.cors_origins_list:
                return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
            if request.cookies.get(settings.SESSION_COOKIE_NAME) and request.url.path not in CSRF_EXEMPT:
                cookie = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
                header = request.headers.get("x-csrf-token", "")
                if not cookie or not header or not hmac.compare_digest(cookie, header):
                    return JSONResponse({"detail": "Missing or invalid CSRF token. Refresh the page and try again."},
                                        status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
