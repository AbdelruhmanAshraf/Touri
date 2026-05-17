"""
Tavily live-web search tool (asynchronous).

Exposes a small async surface that the agents (Phase 2+) can call to fetch
real-time travel facts (flight prices, event updates, currency rates, etc.)
and receive an LLM-ready context string.

Notes
-----
- ``tavily-python`` ships ``TavilyClient`` synchronously and ``AsyncTavilyClient``
  starting in newer releases. To stay compatible with older pins we detect at
  import time and gracefully fall back to ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)

# ── Tavily import (tolerant) ──────────────────────────────────────────────────
try:
    from tavily import TavilyClient  # type: ignore
except Exception as exc:  # noqa: BLE001
    TavilyClient = None  # type: ignore[assignment]
    logger.warning("[tavily] tavily-python not installed: %s", exc)

try:
    from tavily import AsyncTavilyClient  # type: ignore
except Exception:  # pragma: no cover - older versions
    AsyncTavilyClient = None  # type: ignore[assignment]


# ── Public types ──────────────────────────────────────────────────────────────
@dataclass
class WebSearchHit:
    title: str
    url: str
    content: str
    score: float = 0.0

    def as_markdown(self, *, max_chars: int = 800) -> str:
        snippet = (self.content or "").strip().replace("\n", " ")
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 1].rstrip() + "…"
        return f"### {self.title}\n{snippet}\nSource: {self.url}"


@dataclass
class WebSearchResult:
    query: str
    answer: Optional[str]
    hits: List[WebSearchHit]

    def as_llm_context(self, *, max_hits: int = 5, max_chars: int = 800) -> str:
        """Single string optimised for LLM consumption."""
        chunks: List[str] = [f"Live web search: {self.query}"]
        if self.answer:
            chunks.append(f"\n**Tavily summary:** {self.answer.strip()}")
        if self.hits:
            chunks.append("\n**Top sources:**")
            for h in self.hits[:max_hits]:
                chunks.append(h.as_markdown(max_chars=max_chars))
        return "\n\n".join(chunks).strip()


# ── Internals ─────────────────────────────────────────────────────────────────
def _has_key() -> bool:
    return bool(settings.TAVILY_API_KEY)


async def _raw_search(
    query: str,
    *,
    max_results: int,
    search_depth: str,
    include_domains: Optional[List[str]],
    topic: str,
) -> Dict[str, Any]:
    """Hit Tavily, preferring async client; fall back to a worker thread."""
    if not _has_key() or TavilyClient is None:
        raise RuntimeError("Tavily is not configured (missing TAVILY_API_KEY or library).")

    kwargs = dict(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        topic=topic,
        include_answer=True,
        include_raw_content=False,
        include_images=False,
    )
    if include_domains:
        kwargs["include_domains"] = include_domains

    if AsyncTavilyClient is not None:
        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        return await client.search(**kwargs)  # type: ignore[arg-type]

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return await asyncio.to_thread(client.search, **kwargs)


# ── Public API ────────────────────────────────────────────────────────────────
async def search_live_travel_data(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "advanced",  # "basic" | "advanced"
    topic: str = "general",          # "general" | "news"
    include_domains: Optional[List[str]] = None,
) -> WebSearchResult:
    """
    Run a Tavily search optimised for travel-context retrieval.

    Returns a ``WebSearchResult`` with a Tavily-generated answer summary and
    the top hits. Use ``.as_llm_context()`` to fold it into an LLM prompt.
    """
    raw = await _raw_search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_domains=include_domains,
        topic=topic,
    )

    hits: List[WebSearchHit] = []
    for item in raw.get("results", []) or []:
        hits.append(
            WebSearchHit(
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                content=str(item.get("content") or "").strip(),
                score=float(item.get("score") or 0.0),
            )
        )

    return WebSearchResult(
        query=query,
        answer=(raw.get("answer") or None),
        hits=hits,
    )


async def healthcheck() -> Dict[str, Any]:
    """Lightweight probe used by the FastAPI startup hook."""
    if not _has_key():
        return {"ok": False, "reason": "missing TAVILY_API_KEY"}
    if TavilyClient is None:
        return {"ok": False, "reason": "tavily-python not installed"}
    try:
        res = await search_live_travel_data(
            "Tripmind connectivity test query: Cairo travel today",
            max_results=1,
            search_depth="basic",
        )
        return {"ok": True, "hits": len(res.hits), "has_answer": bool(res.answer)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)}


__all__ = [
    "WebSearchHit",
    "WebSearchResult",
    "search_live_travel_data",
    "healthcheck",
]
