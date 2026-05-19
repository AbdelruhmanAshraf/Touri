"""
Production-grade rate limiting for Touri backend.

Uses an in-memory sliding window implementation that is Redis/Upstash-compatible
in interface. Swap the backend store for Redis in horizontal scaling scenarios.

Provides:
- Per-user rate limiting (keyed by authenticated user_id)
- Per-IP rate limiting (fallback for unauthenticated endpoints)
- Separate limit tiers for auth, AI, and general endpoints
- Proper 429 responses with Retry-After headers
- Abuse logging
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("touri.ratelimit")


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit bucket."""

    max_requests: int
    window_seconds: int
    key_prefix: str = ""


# ── Preset rate limit tiers ───────────────────────────────────────────────────
AUTH_LIMIT = RateLimitConfig(max_requests=5, window_seconds=60, key_prefix="auth")
AI_CHAT_LIMIT = RateLimitConfig(max_requests=30, window_seconds=60, key_prefix="ai_chat")
GENERAL_LIMIT = RateLimitConfig(max_requests=60, window_seconds=60, key_prefix="general")
ONBOARDING_LIMIT = RateLimitConfig(max_requests=10, window_seconds=60, key_prefix="onboard")


# ── In-memory sliding window store ───────────────────────────────────────────
# For production at scale, replace with Redis ZRANGEBYSCORE + ZADD pattern.
_store: Dict[str, List[float]] = defaultdict(list)
_MAX_STORE_ENTRIES = 100_000  # prevent unbounded memory growth


def _cleanup_store() -> None:
    """Periodically evict expired entries to prevent memory leak."""
    if len(_store) > _MAX_STORE_ENTRIES:
        cutoff = time.time() - 3600  # Remove entries older than 1 hour
        keys_to_remove = []
        for key, timestamps in _store.items():
            _store[key] = [ts for ts in timestamps if ts > cutoff]
            if not _store[key]:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del _store[key]


def _check_rate_limit(key: str, config: RateLimitConfig) -> Tuple[bool, int, int]:
    """
    Check if the given key has exceeded its rate limit.

    Returns: (allowed, remaining, retry_after_seconds)
    """
    now = time.time()
    window_start = now - config.window_seconds
    full_key = f"{config.key_prefix}:{key}"

    # Sliding window: keep only timestamps within the current window
    _store[full_key] = [ts for ts in _store[full_key] if ts > window_start]
    current_count = len(_store[full_key])

    if current_count >= config.max_requests:
        # Calculate retry-after from oldest timestamp in window
        oldest = min(_store[full_key]) if _store[full_key] else now
        retry_after = int(config.window_seconds - (now - oldest)) + 1
        return False, 0, max(1, retry_after)

    # Allow the request
    _store[full_key].append(now)
    remaining = config.max_requests - current_count - 1

    # Periodic cleanup
    if len(_store) > _MAX_STORE_ENTRIES // 2:
        _cleanup_store()

    return True, remaining, 0


def _get_client_key(request: Request, user_id: Optional[str] = None) -> str:
    """Derive the rate limit key from user_id (preferred) or client IP."""
    if user_id:
        return f"user:{user_id}"
    # Fallback to IP (handles X-Forwarded-For from reverse proxy)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


# ── Public API for route-level rate limiting ──────────────────────────────────
def check_rate_limit_or_raise(
    request: Request,
    config: RateLimitConfig,
    user_id: Optional[str] = None,
) -> None:
    """
    Check rate limit and raise HTTP 429 if exceeded.
    Call this at the top of protected route handlers.
    """
    key = _get_client_key(request, user_id)
    allowed, remaining, retry_after = _check_rate_limit(key, config)

    if not allowed:
        logger.warning(
            "[ratelimit] %s exceeded %s limit (%d/%ds)",
            key,
            config.key_prefix,
            config.max_requests,
            config.window_seconds,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(config.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + retry_after),
            },
        )
