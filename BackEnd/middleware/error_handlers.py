"""
Centralized exception handlers for Touri production backend.

SECURITY: Never expose stack traces, internal paths, LangGraph internals,
or system prompts in error responses. All exceptions are caught and replaced
with safe generic messages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("touri.errors")

ENVIRONMENT = os.environ.get("TOURI_ENV", "production").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# ── Generic safe error messages ───────────────────────────────────────────────
_SAFE_500 = "An internal error occurred. Please try again later."
_SAFE_422 = "Invalid request format. Please check your input."
_SAFE_503 = "Service temporarily unavailable. Please try again later."
_SAFE_504 = "The request timed out. Please try again."
_SAFE_429 = "Too many requests. Please slow down."


def _request_id(request: Request) -> str:
    """Return the request-id header if present, otherwise generate one."""
    return request.headers.get("x-request-id") or uuid.uuid4().hex[:12]


def install_error_handlers(app: FastAPI) -> None:
    """Register production-safe exception handlers on the FastAPI app."""

    @app.exception_handler(asyncio.TimeoutError)
    async def timeout_handler(request: Request, exc: asyncio.TimeoutError) -> JSONResponse:
        rid = _request_id(request)
        logger.warning("[timeout] %s %s rid=%s", request.method, request.url.path, rid)
        return JSONResponse(
            status_code=504,
            content={"code": "TIMEOUT", "message": _SAFE_504, "request_id": rid},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        rid = _request_id(request)
        detail = exc.detail
        if exc.status_code == 429:
            retry_after = (getattr(exc, "headers", None) or {}).get("Retry-After", "30")
            return JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMITED", "message": _SAFE_429, "request_id": rid},
                headers={"Retry-After": str(retry_after)},
            )
        if IS_PRODUCTION and exc.status_code >= 500:
            logger.error("[error] %s %s -> %d: %s rid=%s", request.method, request.url.path, exc.status_code, detail, rid)
            detail = _SAFE_500
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail, "request_id": rid},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = _request_id(request)
        if IS_PRODUCTION:
            logger.warning("[validation] %s %s: %s rid=%s", request.method, request.url.path, str(exc.errors())[:200], rid)
            return JSONResponse(
                status_code=422,
                content={"detail": _SAFE_422, "request_id": rid},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "request_id": rid},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        logger.error(
            "[unhandled] %s %s: %s rid=%s\n%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            rid,
            traceback.format_exc() if not IS_PRODUCTION else "(suppressed)",
        )
        if IS_PRODUCTION:
            return JSONResponse(
                status_code=500,
                content={"detail": _SAFE_500, "request_id": rid},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {str(exc)[:200]}", "request_id": rid},
        )
