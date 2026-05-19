"""
Image resolver for non-attraction catalog items.

Attractions ship with curated ``image_urls`` already. For hotels, restaurants,
transport, flights, events and medical facilities we have nothing, so we
look up a representative photo on the public web at first request and cache
the result on disk.

Resolution order:
    1. Persistent on-disk cache (``data/image_cache.json``).
    2. Wikipedia REST summary endpoint (free, no API key) — best when the
       entity has a Wiki page (most hotels, big events, museums).
    3. Source.unsplash.com curated keyword URL — never 404s, always returns
       a different photo, so we cache the resolved 302 target.

Anything that fails gracefully degrades to an empty string — the UI shows a
themed placeholder card instead of a broken image.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

from config import BACKEND_DIR

logger = logging.getLogger(__name__)

CACHE_FILE = BACKEND_DIR / "data" / "image_cache.json"
WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"

# Wikimedia requires a descriptive UA with a contact handle for non-trivial use.
_HEADERS = {
    "User-Agent": (
        "Touri/0.1 (catalog image resolver; "
        "https://github.com/touri/touri; bot@touri.local)"
    )
}

_CATEGORY_KEYWORDS = {
    "hotel": ["hotel interior", "luxury hotel"],
    "restaurant": ["restaurant interior", "egyptian food", "dining"],
    "transport": ["egypt train", "bus station", "highway egypt"],
    "flight": ["egyptair airplane", "airport terminal"],
    "event": ["festival stage", "concert crowd", "egypt event"],
    "medical": ["hospital ward", "medical clinic", "doctor"],
    "attraction": ["egypt landmark", "egypt historical site"],
}


class _Cache:
    """Tiny JSON-backed cache. Loaded once per process; flushed on update."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, str] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[image_cache] failed to read %s: %s", self.path, exc)
            self._data = {}
        self._loaded = True

    def get(self, key: str) -> Optional[str]:
        self._load()
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._load()
        with self._lock:
            self._data[key] = value
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # Snapshot under the lock to avoid "dict changed during iteration".
                payload = json.dumps(dict(self._data), ensure_ascii=False, indent=2)
                self.path.write_text(payload, "utf-8")
            except Exception as exc:  # noqa: BLE001
                logger.warning("[image_cache] failed to write %s: %s", self.path, exc)


_cache = _Cache(CACHE_FILE)


def _slug_key(category: str, name: str, city: str) -> str:
    base = f"{category}::{name}::{city}".lower().strip()
    return re.sub(r"\s+", " ", base)


def _wiki_summary(title: str) -> Optional[str]:
    """Look up a Wikipedia page summary and return ``thumbnail.source`` if present."""
    try:
        url = WIKI_API + urllib.parse.quote(title.replace(" ", "_"))
        r = httpx.get(url, timeout=4.0, follow_redirects=True, headers=_HEADERS)
        if r.status_code == 200:
            data = r.json()
            thumb = (data.get("thumbnail") or {}).get("source")
            if thumb:
                return thumb
            original = (data.get("originalimage") or {}).get("source")
            if original:
                return original
    except Exception as exc:  # noqa: BLE001
        logger.debug("[image] wiki summary failed for %s: %s", title, exc)
    return None


def _wiki_search_then_summary(query: str) -> Optional[str]:
    """First search Wikipedia, then fetch the top hit's summary thumbnail."""
    try:
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 1,
        }
        r = httpx.get(WIKI_SEARCH, params=params, timeout=4.0, headers=_HEADERS)
        if r.status_code == 200:
            hits = ((r.json() or {}).get("query") or {}).get("search") or []
            if hits:
                return _wiki_summary(hits[0]["title"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("[image] wiki search failed for %s: %s", query, exc)
    return None


def _openverse_image(query: str) -> Optional[str]:
    """Search Openverse (CC-licensed image aggregator across Commons, Flickr, etc).

    Free, no API key required. Much broader photo coverage than Wikipedia
    summaries — handles generic queries like 'hotel interior cairo' well.
    """
    try:
        params = {
            "q": query,
            "page_size": 5,
            "license_type": "all",
            "mature": "false",
        }
        r = httpx.get(OPENVERSE_API, params=params, timeout=6.0, headers=_HEADERS)
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        for item in results:
            url = item.get("thumbnail") or item.get("url")
            if url and isinstance(url, str) and url.startswith("http"):
                return url
    except Exception as exc:  # noqa: BLE001
        logger.debug("[image] openverse search failed for %s: %s", query, exc)
    return None


def _picsum_fallback(category: str, name: str, city: str) -> str:
    """Deterministic Picsum URL — always 200, stable per (category, name, city).

    Replaces the dead source.unsplash.com endpoint. Picsum doesn't pick a
    topical photo, but it always renders a real image so cards never look
    broken.
    """
    sig = re.sub(r"[^a-z0-9]+", "", f"{category}{name}{city}".lower())[:48] or "touri"
    return f"https://picsum.photos/seed/{sig}/800/600"


def resolve_image(*, category: str, name: str, city: str = "") -> str:
    """Return a stable image URL for the given catalog entity.

    Always succeeds — falls back to an Unsplash keyword URL if nothing else
    is available. The cache layer makes subsequent lookups instant.
    """
    if not name:
        return ""
    key = _slug_key(category, name, city)
    cached = _cache.get(key)
    # Discard any stale entries from the dead source.unsplash.com fallback.
    if cached and "source.unsplash.com" in cached:
        cached = None
    if cached:
        return cached

    candidates = [name]
    if city:
        candidates.append(f"{name} {city}")
        candidates.append(f"{name}, {city}")
    if category == "hotel":
        candidates.append(f"{name} hotel")
    elif category == "restaurant":
        candidates.append(f"{name} restaurant")
    elif category == "event":
        candidates.append(f"{name} festival")

    # 1) Wikipedia summary by exact title.
    for title in candidates:
        url = _wiki_summary(title)
        if url:
            _cache.set(key, url)
            return url

    # 2) Wikipedia full-text search.
    url = _wiki_search_then_summary(f"{name} {city}".strip())
    if url:
        _cache.set(key, url)
        return url

    # 3) Openverse — broad CC-licensed photo pool. Try the entity, then
    #    category-generic keywords (e.g. "hotel interior cairo").
    queries = [f"{name} {city}".strip()]
    for kw in _CATEGORY_KEYWORDS.get(category, []):
        queries.append(f"{kw} {city}".strip() if city else kw)
    for q in queries:
        url = _openverse_image(q)
        if url:
            _cache.set(key, url)
            return url

    # 4) Last resort — Picsum seeded URL. Always 200, stable per item.
    url = _picsum_fallback(category, name, city)
    _cache.set(key, url)
    return url


def prefetch_for_items(items: list, max_items: int = 100) -> None:
    """Best-effort prefetch — used by the home endpoint to warm the cache."""
    for it in items[:max_items]:
        # Only resolve for entities that don't already have an image
        existing = getattr(it, "image_urls", None) or []
        if existing:
            continue
        try:
            resolved = resolve_image(category=it.type, name=it.name, city=it.city)
            if resolved:
                it.image_urls = [resolved]
        except Exception as exc:  # noqa: BLE001
            logger.debug("[image] prefetch failed for %s: %s", it.name, exc)


__all__ = ["resolve_image", "prefetch_for_items"]
