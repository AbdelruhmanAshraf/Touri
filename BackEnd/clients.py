"""
Lazy, singleton initialisers for external SDK clients.

Keeps secrets out of business logic: every module imports its client from
here instead of reading env vars itself.

    from clients import gemini, tavily, firebase

    gemini.generate_content("Plan me a trip to Cairo")
    tavily.search("best time to visit Petra")
    firebase.firestore().collection("users").document(uid).get()
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from config import get_settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    import google.generativeai as genai
    from tavily import TavilyClient
    import firebase_admin


# ── Google Gemini (google-generativeai) ──────────────────────────────────────
@lru_cache(maxsize=1)
def get_gemini():
    """Return a configured `google.generativeai.GenerativeModel`."""
    import google.generativeai as genai  # local import → optional dep

    s = get_settings()
    genai.configure(api_key=s.GOOGLE_AI_STUDY_API_KEY)
    logger.info("Gemini client initialised (model=%s)", s.GEMINI_MODEL)
    return genai.GenerativeModel(s.GEMINI_MODEL)


# ── Tavily ───────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_tavily():
    """Return a configured `tavily.TavilyClient`."""
    from tavily import TavilyClient

    s = get_settings()
    logger.info("Tavily client initialised")
    return TavilyClient(api_key=s.TAVILY_API_KEY)


# ── Firebase Admin ───────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_firebase_app():
    """Initialise and return the default Firebase Admin app (singleton)."""
    import firebase_admin
    from firebase_admin import credentials

    s = get_settings()
    sa_path = s.FIREBASE_SERVICE_ACCOUNT_JSON
    if not sa_path.exists():
        raise FileNotFoundError(
            f"Firebase service-account JSON not found at: {sa_path}\n"
            f"Download it from Firebase Console → Project Settings → "
            f"Service Accounts, and set FIREBASE_SERVICE_ACCOUNT_JSON in .env."
        )

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(sa_path))
        firebase_admin.initialize_app(
            cred,
            {
                "projectId": s.FIREBASE_PROJECT_ID,
                "storageBucket": s.FIREBASE_STORAGE_BUCKET,
            },
        )
        logger.info("Firebase Admin initialised (project=%s)", s.FIREBASE_PROJECT_ID)
    return firebase_admin.get_app()


def get_firestore():
    """Return a Firestore client (initialises Firebase if needed)."""
    from firebase_admin import firestore

    get_firebase_app()
    return firestore.client()


# Public aliases — convenient `from clients import gemini, tavily` style
class _Lazy:
    def __init__(self, factory):
        self._factory = factory

    def __getattr__(self, item):
        return getattr(self._factory(), item)

    def __call__(self, *args, **kwargs):
        return self._factory()(*args, **kwargs)


gemini = _Lazy(get_gemini)
tavily = _Lazy(get_tavily)
firestore_db = _Lazy(get_firestore)


__all__ = [
    "get_gemini",
    "get_tavily",
    "get_firebase_app",
    "get_firestore",
    "gemini",
    "tavily",
    "firestore_db",
]
