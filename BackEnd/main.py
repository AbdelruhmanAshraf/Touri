"""
Tripmind FastAPI — Phase 2 multi-agent backend.

Surfaces REST + WebSocket endpoints for the LangGraph multi-agent workflow
(router → travel_planner / budget_specialist / local_concierge / general),
persona CRUD backed by Firestore, and real-time token streaming to the
Expo mobile frontend.

Startup verification covers three foundational subsystems:

    1. ChromaDB persistent store (egypt_travel_knowledge, multilingual EN+AR)
    2. Tavily live web search
    3. Firebase Admin SDK + Firestore

Each subsystem fails *softly*: a warning is logged and the server still
starts, so you can incrementally fill in credentials in ``backend/.env``
and re-verify by reloading.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from data import catalog as catalog_data
from memory import firebase_client
from rag import vector_store
from routes.catalog import router as catalog_router
from routes.chat import router as chat_router
from tools import web_search

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("tripmind")


# ── Startup verification ──────────────────────────────────────────────────────
async def _verify_chroma() -> Dict[str, Any]:
    logger.info("→ verifying ChromaDB at %s", settings.chroma_persist_dir)
    ready = vector_store.is_ready()
    count = vector_store.collection_size() if ready else 0
    if ready:
        logger.info(
            "✓ ChromaDB ready — collection=%s, documents=%d",
            settings.CHROMA_COLLECTION,
            count,
        )
    else:
        logger.warning("✗ ChromaDB not ready (see warnings above).")
    return {
        "ok": ready,
        "collection": settings.CHROMA_COLLECTION,
        "documents": count,
        "persist_dir": str(settings.chroma_persist_dir),
        "embedding_model": settings.EMBEDDING_MODEL,
    }


async def _verify_tavily() -> Dict[str, Any]:
    logger.info("→ verifying Tavily live search")
    result = await web_search.healthcheck()
    if result.get("ok"):
        logger.info(
            "✓ Tavily reachable — test query returned %d hits (answer=%s)",
            result.get("hits", 0),
            "yes" if result.get("has_answer") else "no",
        )
    else:
        logger.warning("✗ Tavily not reachable: %s", result.get("reason"))
    return result


async def _verify_firebase() -> Dict[str, Any]:
    logger.info("→ verifying Firebase Admin SDK")
    info = firebase_client.status()
    if info.get("ok"):
        logger.info(
            "✓ Firebase connected — project=%s",
            info.get("project_id") or "(unknown)",
        )
    else:
        logger.warning("✗ Firebase not ready: %s", info.get("error"))
    return info


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Tripmind backend booting (%s)", settings.APP_VERSION)
    logger.info("=" * 60)

    missing = settings.missing_keys()
    if missing:
        logger.warning(
            "Missing env vars (will degrade gracefully): %s", ", ".join(missing)
        )

    # Warm the in-memory catalog so first requests are instant.
    try:
        items = catalog_data.load_catalog()
        logger.info("✓ Catalog loaded — %d items across all domains.", len(items))
    except Exception as exc:  # noqa: BLE001
        logger.warning("✗ Catalog failed to load: %s", exc)

    app.state.verification = {
        "chroma": await _verify_chroma(),
        "tavily": await _verify_tavily(),
        "firebase": await _verify_firebase(),
    }

    logger.info("-" * 60)
    logger.info("Boot complete. Listening on http://%s:%d", settings.HOST, settings.PORT)
    logger.info("-" * 60)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Dynamic CORS — driven by `CORS_ORIGINS` in .env. Use `*` for fully open dev.
_origins = settings.CORS_ORIGINS or ["*"]
_use_credentials = _origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_use_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 2 routes (REST chat + persona + WebSocket streaming).
app.include_router(chat_router)

# Catalog routes (home feed, place detail, search, categories).
app.include_router(catalog_router)


@app.get("/", tags=["meta"])
async def root() -> Dict[str, Any]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": 2,
        "message": "Tripmind Phase 2 multi-agent backend is online.",
    }


@app.get("/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    """Aggregate readiness probe — covers Chroma, Tavily, Firebase."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "missing_env": settings.missing_keys(),
        "subsystems": getattr(app.state, "verification", None)
        or {
            "chroma": {"ok": vector_store.is_ready()},
            "tavily": {"ok": bool(settings.TAVILY_API_KEY)},
            "firebase": {"ok": firebase_client.is_ready()},
        },
    }
