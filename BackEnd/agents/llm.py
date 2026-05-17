"""
Shared LLM client factory — AgentRouter (OpenAI-compatible) backend.

AgentRouter exposes an OpenAI-compatible API at
``https://agentrouter.org/v1``, so we use ``langchain-openai`` with
``base_url`` and ``api_key`` overrides.  The same ``get_llm`` / ``lang_directive``
/ ``t`` helpers as before are kept so no agent file needs to change.

Model split:
    FAST_MODEL  — claude-haiku-4-5-20251001
                  Used by: Router (intent), General Chat, streaming echo.
                  Fast, cheap, good at tool-use and structured JSON.

    DEFAULT_MODEL — claude-opus-4-6
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
    "AGENT_ROUTER_PRO_MODEL", settings.AGENT_ROUTER_PRO_MODEL
)
FAST_MODEL: str = os.environ.get(
    "AGENT_ROUTER_FAST_MODEL", settings.AGENT_ROUTER_FAST_MODEL
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
    """Cached ChatOpenAI instance pointing at the AgentRouter endpoint.

    The cache is keyed on (model, temperature, streaming) so each unique
    combination creates exactly one client object for the process lifetime.
    """
    # Import here so startup doesn't fail if langchain_openai is missing.
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "langchain-openai is not installed. Run: pip install langchain-openai"
        ) from exc

    api_key = settings.AGENT_ROUTER_API_KEY
    if not api_key:
        raise RuntimeError(
            "AGENT_ROUTER_API_KEY is not configured (see backend/.env)."
        )

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base=settings.AGENT_ROUTER_BASE_URL,
        max_tokens=2048,
        streaming=streaming,
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
