"""
Persistent ChromaDB store for the ``egypt_travel_knowledge`` collection.

Architecture
------------
- One persistent ``chromadb.PersistentClient`` rooted at ``settings.chroma_persist_dir``.
- Embeddings come from a multilingual SentenceTransformers model
  (``paraphrase-multilingual-MiniLM-L12-v2`` by default) so EN/AR queries
  match the same knowledge base.
- Documents are batched on upsert so ingesting all of Egypt's CSVs stays
  efficient regardless of corpus size.

Public surface
--------------
``get_collection()``               Lazily build / return the Chroma Collection.
``index_documents(docs)``          Upsert a list of ``Document`` chunks.
``ingest_egypt_dataset(reset)``    Convenience: load every Egypt file and index it.
``query(text, top_k, filters)``    Semantic search with relevance scoring.
``collection_size()``              Cheap document count for verification logs.
``is_ready()``                     True if the collection exists and is queryable.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from config import settings
from rag.document_loader import Document, load_all_egypt_documents

logger = logging.getLogger(__name__)


_BATCH_SIZE = 50


# ── Client / collection ───────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=str(settings.chroma_persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )


class _GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Direct multilingual embedder backed by ``google-generativeai``.

    Chroma's bundled ``GoogleGenerativeAiEmbeddingFunction`` is broken
    against current ``google-generativeai`` versions, so we call the SDK
    ourselves. Several model names are tried in priority order; the first
    one the installed SDK + endpoint supports wins.
    """

    _MODEL_CANDIDATES = (
        # Probe order — first one the account/SDK supports wins.
        # text-embedding-004 is preferred: multilingual, 768-dim, and has
        # a separate daily quota from the newer gemini-embedding-* family.
        "models/text-embedding-004",
        "models/gemini-embedding-001",
        "models/gemini-embedding-2",
        "models/gemini-embedding-2-preview",
        "models/embedding-001",
    )

    def __init__(self, api_key: str) -> None:
        import google.generativeai as genai  # lazy import keeps module optional

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model = self._pick_model()

    def _pick_model(self) -> str:
        last_exc: Exception | None = None
        for name in self._MODEL_CANDIDATES:
            try:
                # Probe with a tiny payload to discover which model the
                # currently-installed SDK version is actually allowed to call.
                self._genai.embed_content(
                    model=name, content="probe", task_type="retrieval_document"
                )
                return name
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue
        raise RuntimeError(f"No Gemini embedding model usable: {last_exc}")

    # Embed a batch. We split into small sub-batches and auto-retry on
    # 429s so free-tier accounts can complete a full re-ingest without
    # manual babysitting. A cooldown pause between successful sub-batches
    # keeps us under the RPM cap proactively.
    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 — Chroma signature
        import time
        from google.api_core.exceptions import ResourceExhausted

        if not input:
            return []

        out: Embeddings = []
        batch = list(input)
        sub = 5  # small sub-batches to stay under free-tier RPM caps
        cooldown = 4.0  # seconds between successful sub-batches
        i = 0
        while i < len(batch):
            chunk = batch[i : i + sub]
            backoff = 10.0
            attempts = 0
            while True:
                try:
                    resp = self._genai.embed_content(
                        model=self._model,
                        content=chunk,
                        task_type="retrieval_document",
                    )
                    emb = (
                        resp.get("embedding")
                        if isinstance(resp, dict)
                        else getattr(resp, "embedding", None)
                    )
                    if emb is None:
                        raise RuntimeError("Gemini embed_content returned no 'embedding' field.")
                    if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
                        out.append(list(emb))
                    else:
                        out.extend(list(v) for v in emb)
                    break  # success — advance to next sub-batch
                except ResourceExhausted as exc:
                    attempts += 1
                    if attempts > 12:
                        raise
                    # Honour server-supplied retry_delay when present.
                    wait = backoff
                    try:
                        for d in getattr(exc, "details", []) or []:
                            secs = getattr(getattr(d, "retry_delay", None), "seconds", None)
                            if secs:
                                wait = max(wait, float(secs) + 1.0)
                    except Exception:
                        pass
                    logger.warning(
                        "[gemini-embed] 429 rate-limited — sleeping %.1fs then retrying (attempt %d)",
                        wait,
                        attempts,
                    )
                    time.sleep(wait)
                    backoff = min(backoff * 1.5, 65.0)
            i += sub
            # Proactive cooldown between sub-batches to avoid hitting RPM cap.
            if i < len(batch):
                time.sleep(cooldown)
        return out


@lru_cache(maxsize=1)
def _embedding_fn():
    """
    Choose the best available embedding backend.

    Priority (when EMBEDDING_BACKEND='auto'):
      1. Gemini ``gemini-embedding-001`` / ``text-embedding-004`` — multilingual
         (EN + AR), no local torch needed; uses ``GEMINI_API_KEY``.
      2. SentenceTransformers ``paraphrase-multilingual-MiniLM-L12-v2`` —
         local multilingual; needs torch>=2.4 (unavailable on Intel macOS).
      3. Chroma's bundled ONNX MiniLM (English-only) — fast, offline.

    Override with ``EMBEDDING_BACKEND=onnx|gemini|sentence_transformers``.
    """
    backend = (settings.EMBEDDING_BACKEND or "auto").lower()

    # Hard override paths --------------------------------------------------
    if backend == "onnx":
        logger.info("[vector_store] EMBEDDING_BACKEND=onnx — forcing ONNX MiniLM (English).")
        return embedding_functions.DefaultEmbeddingFunction()

    if backend == "sentence_transformers":
        fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
        )
        fn(["__probe__"])
        logger.info(
            "[vector_store] EMBEDDING_BACKEND=sentence_transformers — using %s (multilingual EN+AR)",
            settings.EMBEDDING_MODEL,
        )
        return fn

    # 1. Gemini multilingual embeddings (preferred when API key present).
    if backend in ("auto", "gemini") and settings.GEMINI_API_KEY:
        try:
            fn = _GeminiEmbeddingFunction(api_key=settings.GEMINI_API_KEY)
            fn(["__probe__"])  # auth/quota probe
            logger.info(
                "[vector_store] using Gemini text-embedding-004 (multilingual EN+AR)"
            )
            return fn
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[vector_store] Gemini embeddings unavailable (%s) — trying SentenceTransformers.",
                exc,
            )

    # 2. Local multilingual via SentenceTransformers (needs recent torch).
    try:
        fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
        )
        fn(["__probe__"])
        logger.info(
            "[vector_store] using SentenceTransformers embedding: %s",
            settings.EMBEDDING_MODEL,
        )
        return fn
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[vector_store] SentenceTransformers unavailable (%s) — "
            "falling back to Chroma's bundled ONNX MiniLM (English-only).",
            exc,
        )
        return embedding_functions.DefaultEmbeddingFunction()


def get_collection():
    """Lazily create / fetch the ``egypt_travel_knowledge`` collection."""
    return _client().get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        embedding_function=_embedding_fn(),
        metadata={
            "domain": "egypt_travel",
            "version": "phase1",
            "embedding_model": settings.EMBEDDING_MODEL,
        },
    )


# ── Metadata sanitisation ─────────────────────────────────────────────────────
def _sanitise_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma only stores primitives. Strip None and coerce to str/int/float/bool."""
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if v is None or v == "":
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


# ── Ingestion ─────────────────────────────────────────────────────────────────
def index_documents(docs: Sequence[Document]) -> int:
    """Upsert a list of ``Document`` chunks. Returns the count indexed."""
    if not docs:
        return 0
    coll = get_collection()
    total = 0
    for i in range(0, len(docs), _BATCH_SIZE):
        batch = docs[i : i + _BATCH_SIZE]
        coll.upsert(
            ids=[d.id for d in batch],
            documents=[d.text for d in batch],
            metadatas=[_sanitise_metadata(d.metadata) for d in batch],
        )
        total += len(batch)
        logger.info("[vector_store] upserted %d/%d", total, len(docs))
    return total


def ingest_egypt_dataset(*, reset: bool = False) -> int:
    """Load every Egypt CSV/XLSX and (re)index into Chroma."""
    if reset:
        try:
            _client().delete_collection(settings.CHROMA_COLLECTION)
            logger.info("[vector_store] cleared existing collection")
        except Exception as exc:  # noqa: BLE001
            logger.debug("[vector_store] nothing to delete: %s", exc)
        get_collection.cache_clear() if hasattr(get_collection, "cache_clear") else None
    docs = load_all_egypt_documents()
    return index_documents(docs)


# ── Querying ──────────────────────────────────────────────────────────────────
def _distance_to_relevance(d: float | None) -> float:
    """Map Chroma's cosine distance (0 = identical, 2 = opposite) → relevance ∈ [0,1]."""
    if d is None:
        return 0.0
    return max(0.0, 1.0 - float(d) / 2.0)


def query(
    text: str,
    *,
    top_k: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search with relevance scoring.

    Returns a list of dicts:
        {"id", "text", "metadata", "distance", "relevance"}
    sorted from most to least relevant.
    """
    if not text or not text.strip():
        return []
    coll = get_collection()
    if coll.count() == 0:
        logger.debug("[vector_store] collection is empty — returning []")
        return []

    res = coll.query(
        query_texts=[text],
        n_results=top_k,
        where=where or None,
    )

    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    hits: List[Dict[str, Any]] = []
    for i, doc_id in enumerate(ids):
        dist = dists[i] if i < len(dists) else None
        hits.append(
            {
                "id": doc_id,
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dist,
                "relevance": round(_distance_to_relevance(dist), 4),
            }
        )
    return hits


# ── Diagnostics ───────────────────────────────────────────────────────────────
def collection_size() -> int:
    try:
        return get_collection().count()
    except Exception as exc:  # noqa: BLE001
        logger.debug("[vector_store] count failed: %s", exc)
        return 0


def is_ready() -> bool:
    try:
        get_collection()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[vector_store] not ready: %s", exc)
        return False


__all__ = [
    "get_collection",
    "index_documents",
    "ingest_egypt_dataset",
    "query",
    "collection_size",
    "is_ready",
]
