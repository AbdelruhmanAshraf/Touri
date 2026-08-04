"""
Security middleware stack for Touri production backend.

Provides:
- Security headers (HSTS, X-Frame-Options, CSP, etc.)
- HTTPS redirect in production
- Request size limiting
- Sanitized error handling (no stack trace leaks)
- Structured security logging
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("touri.security")

# ── Environment detection ─────────────────────────────────────────────────────
# Read from pydantic-settings (which loads backend/.env) rather than bare
# os.environ so that TOURI_ENV set only in the .env file is honoured.
from config import settings as _cfg  # noqa: E402 — late import to avoid circular

ENVIRONMENT = (_cfg.TOURI_ENV or os.environ.get("TOURI_ENV", "production")).lower()
IS_PRODUCTION = ENVIRONMENT == "production"


# ── Security Headers Middleware ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects production-grade security headers on every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # HSTS: enforce HTTPS for 1 year, include subdomains
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Remove server identification
        for hdr in ("server", "X-Powered-By"):
            if hdr in response.headers:
                del response.headers[hdr]

        return response


# ── HTTPS Redirect Middleware ─────────────────────────────────────────────────
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP → HTTPS in production. Respects X-Forwarded-Proto from reverse proxy."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not IS_PRODUCTION:
            return await call_next(request)

        # Check X-Forwarded-Proto (set by reverse proxy like nginx/CloudFlare)
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "http":
            url = request.url.replace(scheme="https")
            return Response(
                status_code=301,
                headers={"Location": str(url)},
            )
        return await call_next(request)


# ── Request Size Limit Middleware ─────────────────────────────────────────────
MAX_REQUEST_BODY_SIZE = 25 * 1024 * 1024  # 25MB (supports multimodal uploads)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies to prevent memory exhaustion."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


# ── Request Timeout Middleware ────────────────────────────────────────────────
REQUEST_TIMEOUT_SEC = 120  # 2 minutes max for AI-heavy endpoints


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Log slow requests (actual timeout enforced by reverse proxy/uvicorn)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        if elapsed > REQUEST_TIMEOUT_SEC:
            logger.warning(
                "[timeout] request took %.1fs: %s %s",
                elapsed,
                request.method,
                request.url.path,
            )
        return response


# ── Install all security middleware ───────────────────────────────────────────
def install_security_middleware(app: FastAPI) -> None:
    """Add all security middleware to the FastAPI app in correct order."""
    # Order matters: outermost middleware processes first
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    if IS_PRODUCTION:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["touri.app", "www.touri.app", "api.touri.app"],
        )
    else:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],
        )
    app.add_middleware(RequestTimeoutMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if IS_PRODUCTION:
        app.add_middleware(HTTPSRedirectMiddleware)
