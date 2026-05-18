"""
Shared LLM client factory — Google Gemini backend.

Uses ``langchain-google-genai`` (``ChatGoogleGenerativeAI``) so every
LangGraph agent and chain that calls ``get_llm()`` automatically switches to
Gemini without any other code change.

Model split:
    FAST_MODEL    — gemini-2.0-flash
                    Used by: Router (intent), General Chat, streaming echo.
                    Fast, cheap, multimodal, good at tool-use.

    DEFAULT_MODEL — gemini-2.5-flash-preview-05-20
                    Used by: Travel Planner, Budget Specialist.
                    Best reasoning quality for multi-day itinerary generation
                    and multi-domain cost breakdowns.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Literal

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL: str = os.environ.get(
    "GEMINI_PRO_MODEL", "gemini-2.5-flash-preview-05-20"
)
FAST_MODEL: str = os.environ.get(
    "GEMINI_FAST_MODEL", "gemini-2.0-flash"
)
DEFAULT_TEMPERATURE: float = 0.4

Language = Literal["en", "ar"]


@lru_cache(maxsize=8)
def get_llm(
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    streaming: bool = True,
):
    """Cached ChatGoogleGenerativeAI instance.

    The cache is keyed on (model, temperature, streaming) so each unique
    combination creates exactly one client object for the process lifetime.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise RuntimeError(
            "langchain-google-genai is not installed. "
            "Run: pip install langchain-google-genai"
        ) from exc

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured (see backend/.env)."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
        streaming=streaming,
        convert_system_message_to_human=True,
    )


# ── Bilingual prompt helpers ─────────────────────────────────────────────────
LANG_NAME = {"en": "English", "ar": "Arabic"}


def lang_directive(language: Language) -> str:
    """Drop-in system instruction that pins the response language."""
    if language == "ar":
        return (
            "أنت 'TripMind'، مرشد سفر ذكي. أجب دائمًا باللغة العربية الفصحى "
            "بأسلوب ودود وموجز ودقيق، وحافظ على وحدات العملة والمسافات كما هي "
            "في المصادر."
        )
    return (
        "You are 'TripMind', a warm and precise travel concierge. Respond "
        "in English, keep answers concise, and preserve any currency or "
        "distance units from the source data."
    )


def t(language: Language, en: str, ar: str) -> str:
    """Pick the matching string for the active language."""
    return ar if language == "ar" else en


__all__ = ["get_llm", "lang_directive", "t", "Language", "DEFAULT_MODEL", "FAST_MODEL"]
