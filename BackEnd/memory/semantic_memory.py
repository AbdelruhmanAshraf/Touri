from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Literal, Optional

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)

MemoryType = Literal["short_term", "long_term", "episodic", "preference", "behavioral"]

_COLLECTION_NAME = "touri_semantic_memory"
_DEFAULT_TOP_K = 5
_MAX_IMPORTANT_SNIPPET = 240
_MAX_COMPRESS_BATCH = 18


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _stable_hash(*parts: str) -> str:
    payload = "::".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", text.lower())


class SemanticMemoryRecord(BaseModel):
    id: str
    user_id: str
    content: str
    memory_type: MemoryType = "episodic"
    importance: float = 1.0
    recency_score: float = 0.0
    similarity_score: float = 0.0
    session_id: Optional[str] = None
    source_agent: Optional[str] = None
    intent: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    episodic: bool = False
    compressed_from: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class _SentenceTransformersBackend:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        return [list(map(float, vector)) for vector in vectors]


class _HashEmbeddingBackend:
    """Fallback embedding backend when SentenceTransformers is unavailable."""

    dimension = 384

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = np.zeros(self.dimension, dtype=np.float32)
            for token in _tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[index] += sign * (1.0 + min(len(token), 12) / 12.0)
            norm = float(np.linalg.norm(vec))
            if norm:
                vec /= norm
            vectors.append(vec.astype(float).tolist())
        return vectors


@lru_cache(maxsize=1)
def _embedding_backend():
    try:
        backend = _SentenceTransformersBackend(settings.EMBEDDING_MODEL)
        backend.embed(["__probe__"])
        logger.info(
            "[semantic_memory] using SentenceTransformers embedding model: %s",
            settings.EMBEDDING_MODEL,
        )
        return backend
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[semantic_memory] SentenceTransformers unavailable (%s) — using hash embeddings.",
            exc,
        )
        return _HashEmbeddingBackend()


@lru_cache(maxsize=1)
def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=str(settings.chroma_persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )


@lru_cache(maxsize=1)
def get_collection():
    return _client().get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={
            "domain": "semantic_memory",
            "embedding_model": settings.EMBEDDING_MODEL,
        },
    )


class MemoryImportanceScorer:
    """Heuristic importance scorer for semantic memories."""

    _TYPE_WEIGHTS = {
        "short_term": 0.8,
        "episodic": 1.0,
        "behavioral": 1.2,
        "long_term": 1.3,
        "preference": 1.6,
    }

    _SIGNAL_WEIGHTS = {
        "budget": 0.35,
        "price": 0.30,
        "cheap": 0.25,
        "luxury": 0.35,
        "allergy": 0.40,
        "dietary": 0.30,
        "hotel": 0.25,
        "flight": 0.25,
        "avoid": 0.20,
        "prefer": 0.20,
        "favorite": 0.25,
        "love": 0.15,
        "hate": 0.20,
        "booking": 0.20,
        "itinerary": 0.20,
        "destination": 0.25,
    }

    def score(self, memory: Dict[str, Any]) -> float:
        content = _safe_text(memory.get("content") or memory.get("summary"))
        memory_type = _safe_text(memory.get("memory_type") or memory.get("type") or "episodic")

        score = self._TYPE_WEIGHTS.get(memory_type, 1.0)

        lower = content.lower()
        for signal, bonus in self._SIGNAL_WEIGHTS.items():
            if signal in lower:
                score += bonus

        if memory.get("intent") in ("trip_planning", "budget_query"):
            score += 0.15
        if memory.get("session_id"):
            score += 0.05
        if memory.get("compressed_from"):
            score -= 0.10
        if len(content) > 500:
            score += 0.05

        return max(0.1, min(score, 3.0))

    def recency_score(self, memory: Dict[str, Any]) -> float:
        timestamp = memory.get("created_at") or memory.get("updated_at") or memory.get("timestamp")
        parsed = _parse_iso(_safe_text(timestamp))
        if not parsed:
            return 0.35
        age_hours = max((datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0, 0.0)
        return 1.0 / (1.0 + (age_hours / 24.0))


class MemoryRanker:
    """Combine similarity, importance, and recency into a final ranking."""

    def __init__(self, scorer: Optional[MemoryImportanceScorer] = None) -> None:
        self.scorer = scorer or MemoryImportanceScorer()

    def rank(self, memories: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for memory in memories:
            enriched = dict(memory)
            importance = float(enriched.get("importance") or self.scorer.score(enriched))
            recency = float(enriched.get("recency_score") or self.scorer.recency_score(enriched))
            similarity = float(enriched.get("similarity_score") or 0.0)

            # Normalize importance to 0..1 before mixing it with similarity / recency.
            importance_norm = min(max(importance / 3.0, 0.0), 1.0)
            final_score = (0.45 * similarity) + (0.35 * importance_norm) + (0.20 * recency)

            if enriched.get("memory_type") == "preference":
                final_score += 0.05
            if query and query.lower() in _safe_text(enriched.get("content")).lower():
                final_score += 0.05

            enriched["importance"] = importance
            enriched["recency_score"] = recency
            enriched["similarity_score"] = similarity
            enriched["rank_score"] = round(final_score, 6)
            ranked.append(enriched)

        ranked.sort(key=lambda item: item.get("rank_score", 0.0), reverse=True)
        return ranked


def _record_id(record: SemanticMemoryRecord) -> str:
    base = record.id or _stable_hash(
        record.user_id,
        record.session_id or "global",
        record.memory_type,
        record.content[:500],
    )
    return base


def _record_metadata(record: SemanticMemoryRecord) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "user_id": record.user_id,
        "memory_type": record.memory_type,
        "session_id": record.session_id or "",
        "source_agent": record.source_agent or "",
        "intent": record.intent or "",
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "importance": float(record.importance),
        "episodic": bool(record.episodic),
        "compressed_count": len(record.compressed_from),
        "summary_present": bool(record.summary),
    }
    if record.compressed_from:
        metadata["compressed_from_ids"] = json.dumps(record.compressed_from, ensure_ascii=False)
    if record.metadata:
        metadata["extra_metadata"] = json.dumps(record.metadata, ensure_ascii=False)
    return metadata


def _record_document(record: SemanticMemoryRecord) -> str:
    base = _safe_text(record.summary or record.content)
    return base[:5000]


class MemoryRetriever:
    def __init__(self) -> None:
        self.scorer = MemoryImportanceScorer()
        self.ranker = MemoryRanker(self.scorer)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return _embedding_backend().embed(texts)

    def store_memory(self, record: SemanticMemoryRecord) -> SemanticMemoryRecord:
        collection = get_collection()
        record.id = _record_id(record)
        record.updated_at = _now_iso()
        document = _record_document(record)
        metadata = _record_metadata(record)
        embedding = self._embed([document])[0]

        try:
            collection.upsert(
                ids=[record.id],
                documents=[document],
                embeddings=[embedding],
                metadatas=[metadata],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[semantic_memory] store_memory failed: %s", exc)
        return record

    def retrieve(
        self,
        *,
        user_id: str,
        query: str = "",
        top_k: int = _DEFAULT_TOP_K,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[Dict[str, Any]]:
        collection = get_collection()
        where = {"user_id": user_id}

        try:
            if query.strip():
                query_embedding = self._embed([query.strip()])[0]
                result = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=max(top_k * 3, top_k),
                    where=where,
                    include=["documents", "metadatas", "distances", "ids"],
                )
                documents = (result.get("documents") or [[]])[0]
                metadatas = (result.get("metadatas") or [[]])[0]
                distances = (result.get("distances") or [[]])[0]
                ids = (result.get("ids") or [[]])[0]
            else:
                result = collection.get(where=where, include=["documents", "metadatas", "ids"])
                documents = result.get("documents") or []
                metadatas = result.get("metadatas") or []
                distances = [0.0 for _ in documents]
                ids = result.get("ids") or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("[semantic_memory] retrieve failed: %s", exc)
            return []

        memories: List[Dict[str, Any]] = []
        for idx, document in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            memory_type = _safe_text(metadata.get("memory_type") or "episodic")
            if memory_types and memory_type not in memory_types:
                continue

            distance = float(distances[idx]) if idx < len(distances) and distances[idx] is not None else 1.0
            similarity = max(0.0, 1.0 - min(distance, 1.0))

            memories.append(
                {
                    "id": ids[idx] if idx < len(ids) else metadata.get("id", ""),
                    "user_id": metadata.get("user_id", user_id),
                    "content": _safe_text(document),
                    "memory_type": memory_type,
                    "session_id": metadata.get("session_id") or None,
                    "source_agent": metadata.get("source_agent") or None,
                    "intent": metadata.get("intent") or None,
                    "created_at": metadata.get("created_at") or None,
                    "updated_at": metadata.get("updated_at") or None,
                    "importance": float(metadata.get("importance") or 0.0),
                    "recency_score": 0.0,
                    "similarity_score": similarity,
                    "episodic": bool(metadata.get("episodic")),
                    "compressed_from": json.loads(metadata.get("compressed_from_ids", "[]"))
                    if metadata.get("compressed_from_ids")
                    else [],
                    "summary": _safe_text(document) if metadata.get("summary_present") else None,
                    "metadata": {
                        key: value
                        for key, value in metadata.items()
                        if key not in {
                            "user_id",
                            "memory_type",
                            "session_id",
                            "source_agent",
                            "intent",
                            "created_at",
                            "updated_at",
                            "importance",
                            "episodic",
                            "compressed_count",
                            "summary_present",
                            "compressed_from_ids",
                            "extra_metadata",
                        }
                    },
                }
            )

        ranked = self.ranker.rank(memories, query=query)
        return ranked[:top_k]

    def compress(
        self,
        *,
        user_id: str,
        keep_recent: int = 20,
        max_memories: int = 70,
    ) -> int:
        collection = get_collection()
        try:
            result = collection.get(where={"user_id": user_id}, include=["documents", "metadatas", "ids"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[semantic_memory] compress fetch failed: %s", exc)
            return 0

        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        ids = result.get("ids") or []
        if len(ids) <= max_memories:
            return 0

        candidates: List[Dict[str, Any]] = []
        for idx, document in enumerate(documents):
            metadata = metadatas[idx] if idx < len(metadatas) else {}
            memory = {
                "id": ids[idx],
                "content": _safe_text(document),
                "memory_type": metadata.get("memory_type") or "episodic",
                "created_at": metadata.get("created_at"),
                "updated_at": metadata.get("updated_at"),
                "importance": float(metadata.get("importance") or 0.0),
                "recency_score": self.scorer.recency_score(metadata),
                "similarity_score": 0.0,
            }
            memory["rank_score"] = self.ranker.rank([memory])[0]["rank_score"]
            candidates.append(memory)

        candidates.sort(key=lambda item: item.get("rank_score", 0.0))
        protected_ids = {item["id"] for item in candidates[-keep_recent:]}
        compressible = [item for item in candidates if item["id"] not in protected_ids]
        if not compressible:
            return 0

        compressible = compressible[:_MAX_COMPRESS_BATCH]
        summary_lines = [
            f"- {item['content'][:_MAX_IMPORTANT_SNIPPET]}"
            for item in compressible
            if item.get("content")
        ]
        if not summary_lines:
            return 0

        summary_text = "Compressed semantic memories:\n" + "\n".join(summary_lines)
        summary_record = SemanticMemoryRecord(
            id=_stable_hash(user_id, "compressed", summary_text[:400]),
            user_id=user_id,
            content=summary_text,
            summary=summary_text,
            memory_type="long_term",
            importance=1.4,
            source_agent="semantic_memory",
            episodic=False,
            compressed_from=[item["id"] for item in compressible],
            metadata={"compressed": True, "compressed_count": len(compressible)},
        )
        self.store_memory(summary_record)

        try:
            collection.delete(ids=[item["id"] for item in compressible])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[semantic_memory] compression delete failed: %s", exc)

        return len(compressible)

    async def ingest_exchange(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
        intent: Optional[str] = None,
        preference_updates: Optional[Dict[str, Any]] = None,
        itinerary: Optional[Dict[str, Any]] = None,
        source_agent: Optional[str] = None,
    ) -> List[SemanticMemoryRecord]:
        records: List[SemanticMemoryRecord] = []

        user_record = SemanticMemoryRecord(
            id=_stable_hash(user_id, session_id, "user", user_message[:500]),
            user_id=user_id,
            content=user_message,
            memory_type="episodic",
            session_id=session_id,
            source_agent="user",
            intent=intent,
            importance=self.scorer.score({"content": user_message, "memory_type": "episodic", "intent": intent, "session_id": session_id}),
            episodic=True,
        )
        assistant_type: MemoryType = "long_term" if itinerary else "short_term"
        assistant_record = SemanticMemoryRecord(
            id=_stable_hash(user_id, session_id, "assistant", assistant_response[:500]),
            user_id=user_id,
            content=assistant_response,
            memory_type=assistant_type,
            session_id=session_id,
            source_agent=source_agent or "assistant",
            intent=intent,
            importance=self.scorer.score({"content": assistant_response, "memory_type": assistant_type, "intent": intent, "session_id": session_id}),
            episodic=False,
        )
        records.extend([user_record, assistant_record])

        if itinerary:
            itinerary_summary = _safe_text(
                itinerary.get("summary_message")
                or itinerary.get("summary")
                or itinerary.get("city")
                or itinerary.get("destination")
                or "Generated itinerary"
            )
            records.append(
                SemanticMemoryRecord(
                    id=_stable_hash(user_id, session_id, "itinerary", itinerary_summary[:500]),
                    user_id=user_id,
                    content=itinerary_summary,
                    summary=itinerary_summary,
                    memory_type="long_term",
                    session_id=session_id,
                    source_agent=source_agent or "travel_planner",
                    intent="trip_planning",
                    importance=2.0,
                    episodic=False,
                    metadata={"source": "itinerary", "city": itinerary.get("city", "")},
                )
            )

        if preference_updates:
            for key, value in preference_updates.items():
                if value in (None, "", [], {}):
                    continue
                records.append(
                    SemanticMemoryRecord(
                        id=_stable_hash(user_id, session_id, "pref", key, _safe_text(value)[:200]),
                        user_id=user_id,
                        content=f"Preference update: {key} = {_safe_text(value)}",
                        memory_type="preference",
                        session_id=session_id,
                        source_agent=source_agent or "memory_manager",
                        intent=intent,
                        importance=1.8,
                        episodic=False,
                        metadata={"preference_key": key, "preference_value": _safe_text(value)},
                    )
                )

        for record in records:
            self.store_memory(record)

        try:
            self.compress(user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[semantic_memory] compression pass failed: %s", exc)

        return records


semantic_memory_retriever = MemoryRetriever()


async def save_semantic_exchange(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    intent: Optional[str] = None,
    preference_updates: Optional[Dict[str, Any]] = None,
    itinerary: Optional[Dict[str, Any]] = None,
    source_agent: Optional[str] = None,
) -> List[SemanticMemoryRecord]:
    return await semantic_memory_retriever.ingest_exchange(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        assistant_response=assistant_response,
        intent=intent,
        preference_updates=preference_updates,
        itinerary=itinerary,
        source_agent=source_agent,
    )


async def retrieve_semantic_memories(
    *,
    user_id: str,
    query: str,
    top_k: int = _DEFAULT_TOP_K,
    memory_types: Optional[List[MemoryType]] = None,
) -> List[Dict[str, Any]]:
    if not query.strip() and not memory_types:
        return semantic_memory_retriever.retrieve(user_id=user_id, query="", top_k=top_k)
    return semantic_memory_retriever.retrieve(
        user_id=user_id,
        query=query,
        top_k=top_k,
        memory_types=memory_types,
    )


async def compress_semantic_memories(user_id: str) -> int:
    return semantic_memory_retriever.compress(user_id=user_id)


__all__ = [
    "MemoryImportanceScorer",
    "MemoryRanker",
    "MemoryRetriever",
    "SemanticMemoryRecord",
    "compress_semantic_memories",
    "retrieve_semantic_memories",
    "save_semantic_exchange",
    "semantic_memory_retriever",
]

