"""
Touri backend configuration.

Single source of truth for runtime settings, loaded from
``backend/.env`` via pydantic-settings v2.

Usage
-----
    from config import settings
    settings.GEMINI_API_KEY
    settings.chroma_persist_dir
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
EGYPT_CSV_DIR = DATA_DIR / "egypt_csv"
CHROMA_DIR = DATA_DIR / "chroma_db"
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """All environment-driven settings for the Touri backend."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # ── Mistral AI ────────────────────────────────────────────────────────────
    MISTRAL_API_KEY: str = Field(
        default="",
        description="Mistral AI API key — required for all chat agents.",
    )
    MISTRAL_PRO_MODEL: str = Field(
        default="mistral-large-latest",
        description="Default LLM for the LangGraph text agents (Mistral Large).",
    )
    MISTRAL_FAST_MODEL: str = Field(
        default="mistral-small-latest",
        description="Fast text LLM for router / concierge / streaming echo.",
    )

    # ── Google Gemini (fallback / legacy support) ─────────────────────────────
    GEMINI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_AI_STUDY_API_KEY"),
        description="Google AI Studio API key — optional fallback.",
    )
    GEMINI_PRO_MODEL: str = Field(
        default="gemma-4-26b-a4b-it",
        description="Default LLM for the LangGraph text agents (Gemma-4).",
    )
    GEMINI_FAST_MODEL: str = Field(
        default="gemma-4-26b-a4b-it",
        description="Fast text LLM for router / concierge / streaming echo.",
    )

    # ── AgentRouter (kept for backward-compat — no longer the primary LLM) ───
    AGENT_ROUTER_API_KEY: str = Field(
        default="",
        description="Legacy AgentRouter key — unused after Gemini migration.",
    )
    AGENT_ROUTER_BASE_URL: str = Field(
        default="https://agentrouter.org/v1",
        description="Legacy AgentRouter base URL — unused after Gemini migration.",
    )
    AGENT_ROUTER_FAST_MODEL: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Legacy fast model name — unused after Gemini migration.",
    )
    AGENT_ROUTER_PRO_MODEL: str = Field(
        default="claude-opus-4-6",
        description="Legacy pro model name — unused after Gemini migration.",
    )

    TAVILY_API_KEY: str = Field(
        default="",
        description="Tavily Search API key for live web facts.",
    )
    OPENWEATHER_API_KEY: str = Field(
        default="",
        description="OpenWeatherMap API key (current weather + forecast).",
    )
    FIREBASE_CREDENTIALS_PATH: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FIREBASE_CREDENTIALS_PATH", "FIREBASE_SERVICE_ACCOUNT_JSON"
        ),
        description="Filesystem path to the Firebase Admin service account JSON.",
    )

    # ── RAG / Chroma ──────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = Field(default=str(CHROMA_DIR))
    CHROMA_COLLECTION: str = Field(default="egypt_travel_knowledge")
    EMBEDDING_MODEL: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="SentenceTransformers model (multilingual EN/AR).",
    )
    # Force-select an embedding backend. Values: 'gemini' | 'sentence_transformers'
    # | 'onnx' | 'auto' (default — try Gemini → ST → ONNX). Set to 'onnx' if the
    # Gemini free-tier quota is too low for full re-ingestion.
    EMBEDDING_BACKEND: str = Field(default="auto")

    # ── CSV ingestion ─────────────────────────────────────────────────────────
    EGYPT_CSV_DIR: str = Field(default=str(EGYPT_CSV_DIR))

    # ── Session / JWT (Phase 5 secure cookies) ────────────────────────────────
    SESSION_JWT_SECRET: str = Field(
        default="",
        description=(
            "HMAC secret used to sign HTTP-only access + refresh JWTs. "
            "Set explicitly in production; auto-randomised per process if unset."
        ),
    )

    # ── HTTP server ───────────────────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    APP_NAME: str = Field(default="Touri API")
    APP_VERSION: str = Field(default="0.1.0-phase1")

    # ── Environment ────────────────────────────────────────────────────────────
    TOURI_ENV: str = Field(
        default="production",
        description="Runtime environment: 'production' or 'development'. Controls security strictness.",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as a raw string so pydantic-settings doesn't try to JSON-decode it.
    # Use `*` for fully open dev or a comma-separated list, e.g.:
    #   CORS_ORIGINS=*
    #   CORS_ORIGINS=http://localhost:5173,http://192.168.1.88:8081
    CORS_ORIGINS_RAW: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def CORS_ORIGINS(self) -> List[str]:  # noqa: N802 — keep API-style attr name
        raw = (self.CORS_ORIGINS_RAW or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # ── Convenience views ─────────────────────────────────────────────────────
    @property
    def chroma_persist_dir(self) -> Path:
        return Path(self.CHROMA_PERSIST_DIR)

    @property
    def egypt_csv_dir(self) -> Path:
        return Path(self.EGYPT_CSV_DIR)

    @property
    def firebase_credentials_path(self) -> Path | None:
        if not self.FIREBASE_CREDENTIALS_PATH:
            return None
        path = Path(self.FIREBASE_CREDENTIALS_PATH).expanduser()
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    def missing_keys(self) -> list[str]:
        """Return the list of required API keys that are still unset.

        Note: TAVILY_API_KEY is excluded — Touri runs in pure offline RAG mode.
        """
        missing: list[str] = []
        if not self.MISTRAL_API_KEY:
            missing.append("MISTRAL_API_KEY")
        # TAVILY_API_KEY intentionally excluded — bypassed in offline RAG mode.
        if not self.FIREBASE_CREDENTIALS_PATH:
            missing.append("FIREBASE_CREDENTIALS_PATH")
        return missing


# Module-level singleton
settings = Settings()

# Ensure the persistence dir exists so downstream modules can rely on it.
os.makedirs(settings.chroma_persist_dir, exist_ok=True)

if (missing := settings.missing_keys()):
    logger.warning(
        "[config] Missing env vars: %s — populate backend/.env before "
        "running Phase 1 verification.",
        ", ".join(missing),
    )
