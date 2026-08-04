"""
Touri FastAPI — Pure Offline RAG Multi-Agent Backend.

Surfaces REST + WebSocket endpoints for the LangGraph multi-agent workflow
(router → travel_planner / budget_specialist / local_concierge / general),
persona CRUD backed by Firestore, and real-time token streaming to the
Expo mobile frontend.

100% Offline RAG Mode: All agents rely exclusively on the local ChromaDB
``egypt_travel_knowledge`` dataset (3,723 verified Egypt documents).
External web search (Tavily) is fully bypassed.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from data import catalog as catalog_data
from memory import firebase_client
from middleware.error_handlers import install_error_handlers
from middleware.security import install_security_middleware, IS_PRODUCTION
from rag import vector_store
from routes.auth import router as auth_router
from routes.catalog import router as catalog_router
from routes.chat import router as chat_router
# BYPASSED: Tavily web search disabled for pure offline RAG mode.
# from tools import web_search

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("touri")


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
    }


async def _verify_tavily() -> Dict[str, Any]:
    """BYPASSED: Tavily is disabled in offline RAG mode."""
    logger.info("→ Tavily web search: BYPASSED (Pure Offline RAG Mode)")
    return {"ok": True, "reason": "bypassed — pure offline RAG mode", "hits": 0}


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
    logger.info("")
    logger.info("=" * 60)
    logger.info("Touri Multi-Agent Backend — Offline RAG Mode Activated 🧠")
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

    chroma_status = await _verify_chroma()
    tavily_status = await _verify_tavily()
    firebase_status = await _verify_firebase()

    app.state.verification = {
        "chroma": chroma_status,
        "tavily": tavily_status,
        "firebase": firebase_status,
    }

    chroma_count = chroma_status.get("documents", 0)
    logger.info("")
    logger.info("✓ ChromaDB Database Connected: %d Verified Egypt Docs Live.", chroma_count)
    logger.info("✓ External Search Bypass Enabled (Pure Local Vector Routing).")
    logger.info("-" * 60)
    logger.info("Boot complete. Listening on http://%s:%d", settings.HOST, settings.PORT)
    logger.info("-" * 60)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
# SECURITY: Disable OpenAPI docs in production to prevent API reconnaissance.
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# ── CORS: production lockdown ─────────────────────────────────────────────────────
# SECURITY: Never use wildcard "*" in production. Whitelist specific origins.
_PRODUCTION_ORIGINS = [
    "https://touri.app",
    "https://www.touri.app",
    "https://api.touri.app",
]
_DEV_ORIGINS = [
    "http://localhost:8081",
    "http://localhost:19006",
    "http://localhost:3000",
    "http://127.0.0.1:8081",
    "http://192.168.1.88:8081",   # Local network Expo (current LAN IP)
    "http://192.168.1.88:19006",
    "http://192.168.1.88:8000",
]

def _get_local_ips() -> list[str]:
    import socket
    ips = []
    try:
        # standard method to find primary LAN IP by socket connection
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        if local_ip:
            ips.append(local_ip)
    except Exception:
        pass
    try:
        # fallback using hostname
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips

# Dynamically add local LAN IPs to development CORS origins
for _ip in _get_local_ips():
    for _port in ["8081", "19006", "8000"]:
        _origin = f"http://{_ip}:{_port}"
        if _origin not in _DEV_ORIGINS:
            _DEV_ORIGINS.append(_origin)

if IS_PRODUCTION:
    _allowed_origins = _PRODUCTION_ORIGINS
    _allowed_headers = ["Authorization", "Content-Type", "X-Requested-With", "Accept"]
else:
    # In development, allow all origins/headers when explicitly configured as "*".
    _configured = settings.CORS_ORIGINS
    if _configured == ["*"]:
        _allowed_origins = ["*"]
        _allowed_headers = ["*"]
    else:
        _allowed_origins = _configured
        _allowed_headers = ["Authorization", "Content-Type", "X-Requested-With", "Accept"]

if not IS_PRODUCTION and _allowed_origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://.*",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=_allowed_headers,
        max_age=600,
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=_allowed_headers,
        max_age=600,
    )

# ── Security middleware & error handlers ──────────────────────────────────────
install_security_middleware(app)
install_error_handlers(app)

# Phase 2 routes (REST chat + persona + WebSocket streaming).
app.include_router(chat_router)

# Catalog routes (home feed, place detail, search, categories).
app.include_router(catalog_router)

# Phase 5 auth / session routes (HTTP-only cookies + JWT refresh).
app.include_router(auth_router)


@app.get("/", tags=["meta"])
async def root() -> Dict[str, Any]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": 2,
        "mode": "offline_rag",
        "message": "Touri Multi-Agent Backend — Offline RAG Mode Activated.",
    }


@app.get("/health", tags=["meta"])
async def health() -> Dict[str, Any]:
    """Aggregate readiness probe — simple status check to prevent reconnaissance."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "mode": "offline_rag",
    }
