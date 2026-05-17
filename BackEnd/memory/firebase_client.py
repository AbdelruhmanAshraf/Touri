"""
Firebase Admin SDK bootstrap.

Reads the path to a service-account JSON from ``settings.FIREBASE_CREDENTIALS_PATH``
and initialises a single shared Firestore client. Designed to *not* crash the
process if Firebase is misconfigured — instead it logs a warning and exposes
``is_ready()`` so the FastAPI startup hook can report the failure cleanly.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import settings

logger = logging.getLogger(__name__)


_lock = threading.Lock()
_firestore_client: Optional[firestore.Client] = None  # type: ignore[name-defined]
_init_error: Optional[str] = None
_project_id: Optional[str] = None


def _resolve_credentials_path() -> Optional[Path]:
    path = settings.firebase_credentials_path
    if path is None:
        return None
    if not path.exists():
        logger.warning("[firebase] credentials file not found at %s", path)
        return None
    return path


def init_firebase() -> Optional[firestore.Client]:  # type: ignore[name-defined]
    """Idempotently initialise the Firebase Admin SDK + Firestore client."""
    global _firestore_client, _init_error, _project_id

    with _lock:
        if _firestore_client is not None:
            return _firestore_client

        cred_path = _resolve_credentials_path()
        if cred_path is None:
            _init_error = "FIREBASE_CREDENTIALS_PATH is unset or file missing."
            logger.warning("[firebase] %s", _init_error)
            return None

        try:
            if not firebase_admin._apps:  # type: ignore[attr-defined]
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
                logger.info("[firebase] initialised from %s", cred_path)
            app = firebase_admin.get_app()
            _project_id = getattr(app, "project_id", None) or app.options.get(
                "projectId"
            )
            _firestore_client = firestore.client()
            _init_error = None
            return _firestore_client
        except Exception as exc:  # noqa: BLE001
            _init_error = str(exc)
            logger.error("[firebase] init failed: %s", exc, exc_info=True)
            return None


def get_db() -> firestore.Client:  # type: ignore[name-defined]
    """Return the Firestore client, raising if Firebase isn't configured."""
    client = init_firebase()
    if client is None:
        raise RuntimeError(
            f"Firebase is not initialised: {_init_error or 'unknown error'}"
        )
    return client


def is_ready() -> bool:
    return init_firebase() is not None


def status() -> dict:
    """Structured status for `/health` and startup verification logs."""
    ready = is_ready()
    return {
        "ok": ready,
        "project_id": _project_id,
        "credentials_path": str(settings.firebase_credentials_path) if settings.firebase_credentials_path else None,
        "error": _init_error if not ready else None,
    }


__all__ = ["init_firebase", "get_db", "is_ready", "status"]
