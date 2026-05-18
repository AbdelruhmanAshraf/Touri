"""
Shared LLM client factory — Google Gemini / Gemma backend.

Dual interface:
    1. ``get_llm()``         — LangChain ``ChatGoogleGenerativeAI`` wrapper
                               (used by all LangGraph agent nodes).
    2. ``get_gemini_model()`` — Native ``google-generativeai`` GenerativeModel
                               (used for direct streaming, tool-calling, and
                               multimodal paths that bypass LangChain).

Model target: **gemma-4-27b-it**
    Pulled via the Google AI Studio API key (``GEMINI_API_KEY``).
    Exceptionally responsive to structured prompt framing, bilingual
    (EN/AR) reasoning, and Egypt-domain knowledge.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Literal

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL: str = os.environ.get("GEMINI_PRO_MODEL", "gemma-4-27b-it")
FAST_MODEL: str = os.environ.get("GEMINI_FAST_MODEL", "gemma-4-27b-it")
DEFAULT_TEMPERATURE: float = 0.4

Language = Literal["en", "ar"]


# ── Global system instruction block (Gemma-4-27B-IT optimised) ────────────────
GLOBAL_SYSTEM_INSTRUCTION = """\
You are TripMind — a multi-agent AI travel concierge specialised in Egypt tourism.

## Core Directives
1. **Bilingual Processing**: Natively understand queries in Arabic (Egyptian & MSA) and English. Detect the user's language and respond in the same language unless instructed otherwise.
2. **Egypt RAG Grounding**: When RAG context is provided, ground all factual claims strictly in the retrieved data. Never fabricate attraction names, prices, or addresses.
3. **Reasoning Traces**: Before generating your final answer, internally structure your reasoning as: [Intent] → [Relevant Context] → [Plan] → [Response]. This chain-of-thought improves output accuracy.
4. **Persona Awareness**: Always factor in the user's travel persona (tourism type, budget bracket, dietary preference, food allergies, party size) when making recommendations.
5. **Structured Output**: When asked for JSON, return valid JSON only — no markdown fences, no commentary outside the JSON object.
6. **Safety & Accuracy**: Never suggest unsafe activities. Clearly mark estimated prices vs. confirmed prices. Respect dietary restrictions and allergen boundaries absolutely.

## Domain Knowledge
- Egypt's 27 governorates, major cities, archaeological sites, Red Sea resorts, medical tourism facilities, Nile cruises, desert safaris.
- Currency: Egyptian Pound (EGP). Include USD equivalents when relevant.
- Cultural norms: prayer times, Ramadan considerations, dress codes for religious sites.
"""


# ── LangChain wrapper (for LangGraph nodes) ──────────────────────────────────
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
    )


# ── Native Google GenAI SDK model (for streaming / direct calls) ──────────────
@lru_cache(maxsize=4)
def get_gemini_model(
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
):
    """
    Return a native ``google.generativeai.GenerativeModel`` configured with
    the global system instruction. Used for direct ``generate_content`` and
    ``generate_content_async(stream=True)`` calls.
    """
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        ) from exc

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured (see backend/.env).")

    genai.configure(api_key=api_key)

    return genai.GenerativeModel(
        model_name=model,
        system_instruction=GLOBAL_SYSTEM_INSTRUCTION,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
        ),
    )


async def generate_text(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """One-shot text generation via the native SDK. Returns the text response."""
    m = get_gemini_model(model=model, temperature=temperature)
    response = await m.generate_content_async(prompt)
    return response.text or ""


# ── Bilingual prompt helpers ─────────────────────────────────────────────────
LANG_NAME = {"en": "English", "ar": "Arabic"}


def lang_directive(language: Language) -> str:
    """Drop-in system instruction that pins the response language."""
    if language == "ar":
        return (
            "أنت 'TripMind'، مرشد سفر ذكي متخصص في السياحة المصرية. "
            "أجب دائمًا باللغة العربية الفصحى بأسلوب ودود وموجز ودقيق. "
            "حافظ على وحدات العملة والمسافات كما هي في المصادر. "
            "عند معالجة بيانات RAG، استند فقط إلى الحقائق المسترجعة ولا تختلق معلومات. "
            "راعِ دائمًا الحساسية الغذائية والقيود الغذائية للمستخدم."
        )
    return (
        "You are 'TripMind', a warm and precise travel concierge specialised "
        "in Egypt tourism. Respond in English, keep answers concise, and "
        "preserve any currency or distance units from the source data. "
        "When processing RAG context, ground all claims in retrieved facts only. "
        "Always respect the user's food allergies and dietary restrictions."
    )


def t(language: Language, en: str, ar: str) -> str:
    """Pick the matching string for the active language."""
    return ar if language == "ar" else en


__all__ = [
    "get_llm",
    "get_gemini_model",
    "generate_text",
    "lang_directive",
    "t",
    "Language",
    "DEFAULT_MODEL",
    "FAST_MODEL",
    "GLOBAL_SYSTEM_INSTRUCTION",
]
