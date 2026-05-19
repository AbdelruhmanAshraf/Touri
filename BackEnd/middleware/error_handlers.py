"""
Centralized exception handlers for Touri production backend.

SECURITY: Never expose stack traces, internal paths, LangGraph internals,
or system prompts in error responses. All exceptions are caught and replaced
with safe generic messages.
"""

from __future__ import annotations

import logging
import os
import traceback

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


def install_error_handlers(app: FastAPI) -> None:
    """Register production-safe exception handlers on the FastAPI app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # HTTPExceptions are intentional — pass through status and detail
        # but strip any internal info that might have leaked in
        detail = exc.detail
        if IS_PRODUCTION and exc.status_code >= 500:
            # Never expose 5xx details in production
            logger.error(
                "[error] %s %s -> %d: %s",
                request.method,
                request.url.path,
                exc.status_code,
                detail,
            )
            detail = _SAFE_500
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if IS_PRODUCTION:
            logger.warning(
                "[validation] %s %s: %s",
                request.method,
                request.url.path,
                str(exc.errors())[:200],
            )
            return JSONResponse(
                status_code=422,
                content={"detail": _SAFE_422},
            )
        # In development, show validation errors for debugging
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # SECURITY: Never expose internal exceptions in production
        logger.error(
            "[unhandled] %s %s: %s\n%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            traceback.format_exc() if not IS_PRODUCTION else "(suppressed)",
        )
        if IS_PRODUCTION:
            return JSONResponse(
                status_code=500,
                content={"detail": _SAFE_500},
            )
        # Development mode: show more info for debugging
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"{type(exc).__name__}: {str(exc)[:200]}",
            },
        )
