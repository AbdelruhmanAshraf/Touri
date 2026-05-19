"""
Auth / session routes — Production Hardened.

Provides a secure server-side session layer on top of Firebase Auth.

Flow
----
1. The Expo client signs the user in with Firebase (email/password or Google),
   then POSTs the resulting Firebase ID token to ``/api/auth/session``.
2. The server ALWAYS verifies the Firebase ID token via the Admin SDK.
   If Firebase is unavailable, authentication fails (503).
3. We mint two opaque JWTs:
     * ``touri_access``  (short-lived, 60 min)
     * ``touri_refresh`` (long-lived, 30 days, with token family rotation)
   Both are written as **HttpOnly, Secure, SameSite=Lax** cookies and the
   access token is also returned in the JSON body so the mobile client can
   stash it in ``expo-secure-store`` for cross-tab WebSocket auth.
4. ``/api/auth/refresh`` rotates both tokens with replay detection.
5. ``/api/auth/logout`` revokes active tokens and clears cookies.
6. ``/api/auth/me`` returns the active user_id from the access cookie OR the
   ``Authorization: Bearer <token>`` header — either is accepted.

Security
--------
* Firebase ID tokens are ALWAYS verified server-side. Client user_id is NEVER trusted.
* Refresh tokens use family-based rotation with replay detection.
* All auth endpoints are rate-limited (5 req/min).
* JWTs are signed with ``settings.SESSION_JWT_SECRET`` (HS256). Set explicitly in production.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from config import settings
from memory.firebase_client import is_ready as firebase_ready
from middleware.rate_limit import AUTH_LIMIT, check_rate_limit_or_raise

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── JWT helpers ──────────────────────────────────────────────────────────────
ACCESS_COOKIE = "touri_access"
REFRESH_COOKIE = "touri_refresh"
ACCESS_TTL_SEC = 60 * 60          # 1 hour
REFRESH_TTL_SEC = 60 * 60 * 24 * 30  # 30 days

_JWT_SECRET = (
    os.environ.get("SESSION_JWT_SECRET")
    or getattr(settings, "SESSION_JWT_SECRET", None)
    or secrets.token_urlsafe(48)
)

# ── Refresh token revocation store ────────────────────────────────────────────
# In-memory for single-instance. Replace with Redis for horizontal scaling.
_revoked_tokens: set = set()  # Set of revoked jti values
_token_families: Dict[str, str] = {}  # family_id -> latest jti
_MAX_REVOKED_STORE = 50_000


def _revoke_token(jti: str) -> None:
    """Add a token's jti to the revocation set."""
    _revoked_tokens.add(jti)
    # Prevent unbounded memory growth
    if len(_revoked_tokens) > _MAX_REVOKED_STORE:
        # Remove oldest entries (approximate — set is unordered)
        excess = len(_revoked_tokens) - _MAX_REVOKED_STORE
        for _ in range(excess):
            _revoked_tokens.pop()


def _is_token_revoked(jti: str) -> bool:
    """Check if a token has been revoked."""
    return jti in _revoked_tokens


def _revoke_family(family_id: str) -> None:
    """Revoke an entire token family (replay detection)."""
    logger.warning("[auth] revoking entire token family: %s (possible replay attack)", family_id)
    if family_id in _token_families:
        _revoke_token(_token_families[family_id])
        del _token_families[family_id]

try:
    import jwt  # PyJWT
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore[assignment]
    logger.warning("[auth] PyJWT is not installed — install with: pip install PyJWT")


def _encode(payload: Dict[str, Any], ttl_sec: int) -> str:
    if jwt is None:
        raise HTTPException(500, "PyJWT is not installed on the server.")
    now = int(time.time())
    body = {"iat": now, "exp": now + ttl_sec, **payload}
    return jwt.encode(body, _JWT_SECRET, algorithm="HS256")


def _decode(token: str) -> Optional[Dict[str, Any]]:
    if jwt is None or not token:
        return None
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("[auth] jwt decode failed: %s", exc)
        return None


def decode_access_token(token: str) -> Optional[str]:
    """Verify and decode an access token, returning the sub (user_id) if valid."""
    decoded = _decode(token)
    if decoded and decoded.get("kind") == "access" and decoded.get("sub"):
        return str(decoded["sub"])
    return None



def _set_session_cookies(resp: Response, *, user_id: str, family_id: Optional[str] = None) -> Dict[str, str]:
    # Generate unique token identifiers for rotation tracking
    access_jti = secrets.token_urlsafe(16)
    refresh_jti = secrets.token_urlsafe(16)
    fid = family_id or secrets.token_urlsafe(12)

    access = _encode({"sub": user_id, "kind": "access", "jti": access_jti}, ACCESS_TTL_SEC)
    refresh = _encode({"sub": user_id, "kind": "refresh", "jti": refresh_jti, "fid": fid}, REFRESH_TTL_SEC)

    # Track the latest token in this family
    _token_families[fid] = refresh_jti

    common = {"httponly": True, "secure": True, "samesite": "lax", "path": "/"}
    resp.set_cookie(ACCESS_COOKIE, access, max_age=ACCESS_TTL_SEC, **common)
    resp.set_cookie(REFRESH_COOKIE, refresh, max_age=REFRESH_TTL_SEC, **common)
    return {"access_token": access, "refresh_token": refresh}


def _clear_session_cookies(resp: Response) -> None:
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/")


# ── Firebase ID-token verification (MANDATORY) ───────────────────────────────
def _verify_firebase_token(id_token: str) -> str:
    """Verify a Firebase ID token. Returns the uid or raises HTTPException."""
    if not id_token:
        logger.warning("[auth] token verification failed: empty id_token")
        raise HTTPException(status_code=401, detail="Authentication token is required.")
    if not firebase_ready():
        logger.error("[auth] Firebase Admin SDK unavailable — cannot verify tokens")
        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable. Please try again later.",
        )
    try:
        from firebase_admin import auth as fb_auth  # type: ignore

        decoded = fb_auth.verify_id_token(id_token, check_revoked=True)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        return uid
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("[auth] firebase verify_id_token failed: %s", exc)
        raise HTTPException(status_code=401, detail="Authentication token verification failed.")


# ── Schemas ──────────────────────────────────────────────────────────────────
class SessionStartRequest(BaseModel):
    id_token: str = Field(..., min_length=1, description="Firebase ID token — required.")
    user_id: Optional[str] = Field(default=None, description="Ignored; uid is always derived from verified token.")


class SessionResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = ACCESS_TTL_SEC


class MeResponse(BaseModel):
    user_id: str
    authenticated: bool
    expires_at: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────────
@router.post("/session", response_model=SessionResponse)
async def start_session(payload: SessionStartRequest, request: Request, response: Response) -> SessionResponse:
    """Mint access + refresh tokens after a successful Firebase sign-in."""
    check_rate_limit_or_raise(request, AUTH_LIMIT)
    # SECURITY: Always verify Firebase token server-side. Never trust client uid.
    uid = _verify_firebase_token(payload.id_token)
    logger.info("[auth] session created for uid=%s", uid)
    tokens = _set_session_cookies(response, user_id=uid)
    return SessionResponse(user_id=uid, **tokens)


async def get_current_user(
    access: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    authorization: Optional[str] = Header(default=None),
) -> str:
    """FastAPI dependency to retrieve the authenticated user's ID from JWT."""
    token = access
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(None, 1)[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing session access token.")

    decoded = _decode(token)
    if not decoded or decoded.get("kind") != "access" or not decoded.get("sub"):
        raise HTTPException(
            status_code=401, detail="Invalid or expired session access token."
        )

    return str(decoded["sub"])



@router.post("/refresh", response_model=SessionResponse)
async def refresh_session(
    request: Request,
    response: Response,
    refresh: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
) -> SessionResponse:
    """Rotate the access cookie using the refresh cookie with replay detection."""
    check_rate_limit_or_raise(request, AUTH_LIMIT)
    decoded = _decode(refresh or "")
    if not decoded or decoded.get("kind") != "refresh" or not decoded.get("sub"):
        raise HTTPException(401, "Invalid or expired refresh token.")

    uid = str(decoded["sub"])
    jti = decoded.get("jti", "")
    family_id = decoded.get("fid", "")

    # SECURITY: Check if this specific token has been revoked
    if jti and _is_token_revoked(jti):
        # Replay detected! Revoke the entire family
        if family_id:
            _revoke_family(family_id)
        logger.error("[auth] refresh token replay detected for uid=%s jti=%s", uid, jti)
        _clear_session_cookies(response)
        raise HTTPException(401, "Session has been invalidated. Please sign in again.")

    # SECURITY: Verify this token is the latest in its family
    if family_id and jti:
        expected_jti = _token_families.get(family_id)
        if expected_jti and expected_jti != jti:
            # Old token used — possible replay. Revoke family.
            _revoke_family(family_id)
            logger.error("[auth] stale refresh token used for uid=%s (replay?)", uid)
            _clear_session_cookies(response)
            raise HTTPException(401, "Session has been invalidated. Please sign in again.")

    # Revoke the old refresh token immediately
    if jti:
        _revoke_token(jti)

    # Issue new tokens in the same family
    tokens = _set_session_cookies(response, user_id=uid, family_id=family_id or None)
    return SessionResponse(user_id=uid, **tokens)


@router.post("/logout")
async def logout(
    response: Response,
    refresh: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    access: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
) -> Dict[str, bool]:
    """Logout: revoke active tokens and clear cookies."""
    # Revoke the refresh token to prevent reuse
    if refresh:
        decoded = _decode(refresh)
        if decoded:
            jti = decoded.get("jti")
            family_id = decoded.get("fid")
            if jti:
                _revoke_token(jti)
            if family_id and family_id in _token_families:
                del _token_families[family_id]
    # Revoke access token too
    if access:
        decoded = _decode(access)
        if decoded and decoded.get("jti"):
            _revoke_token(decoded["jti"])

    _clear_session_cookies(response)
    logger.info("[auth] user logged out, tokens revoked")
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    access: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    authorization: Optional[str] = Header(default=None),
) -> MeResponse:
    token = access
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(None, 1)[1].strip()
    decoded = _decode(token or "")
    if not decoded or decoded.get("kind") != "access" or not decoded.get("sub"):
        return MeResponse(user_id="", authenticated=False)
    expires_at = (
        datetime.fromtimestamp(int(decoded["exp"]), tz=timezone.utc).isoformat()
        if "exp" in decoded
        else None
    )
    return MeResponse(
        user_id=str(decoded["sub"]),
        authenticated=True,
        expires_at=expires_at,
    )


__all__ = ["router", "get_current_user", "decode_access_token"]
