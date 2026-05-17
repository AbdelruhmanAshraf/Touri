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
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

from config import BACKEND_DIR

logger = logging.getLogger(__name__)

CACHE_FILE = BACKEND_DIR / "data" / "image_cache.json"
WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"

_UNSPLASH_CATEGORY_KEYWORDS = {
    "hotel": "luxury,hotel,interior",
    "restaurant": "restaurant,food,dining",
    "transport": "train,bus,road,egypt",
    "flight": "airplane,airport,sky",
    "event": "festival,crowd,stage,lights",
    "medical": "clinic,hospital,medical",
    "attraction": "egypt,landmark,historical",
}


class _Cache:
    """Tiny JSON-backed cache. Loaded once per process; flushed on update."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, str] = {}
        self._loaded = False

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
        self._data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), "utf-8")
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
        r = httpx.get(url, timeout=4.0, follow_redirects=True,
                      headers={"User-Agent": "Tripmind/0.1 (catalog image resolver)"})
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
        r = httpx.get(WIKI_SEARCH, params=params, timeout=4.0,
                      headers={"User-Agent": "Tripmind/0.1 (catalog image resolver)"})
        if r.status_code == 200:
            hits = ((r.json() or {}).get("query") or {}).get("search") or []
            if hits:
                return _wiki_summary(hits[0]["title"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("[image] wiki search failed for %s: %s", query, exc)
    return None


def _unsplash_fallback(category: str, name: str, city: str) -> str:
    """Build a deterministic source.unsplash.com URL.

    The endpoint always returns 200 with a different photo per (query, sig) pair.
    We embed the slug in ``sig`` so the same item always resolves to the same
    server-picked photo within a session.
    """
    keywords = _UNSPLASH_CATEGORY_KEYWORDS.get(category, "egypt,travel")
    parts = [name, city, keywords, "egypt"]
    query = ",".join(urllib.parse.quote(p) for p in parts if p)
    sig = re.sub(r"[^a-z0-9]+", "", f"{category}{name}{city}".lower())[:24]
    return f"https://source.unsplash.com/featured/800x600/?{query}&sig={sig}"


def resolve_image(*, category: str, name: str, city: str = "") -> str:
    """Return a stable image URL for the given catalog entity.

    Always succeeds — falls back to an Unsplash keyword URL if nothing else
    is available. The cache layer makes subsequent lookups instant.
    """
    if not name:
        return ""
    key = _slug_key(category, name, city)
    cached = _cache.get(key)
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

    for title in candidates:
        url = _wiki_summary(title)
        if url:
            _cache.set(key, url)
            return url

    # Wikipedia full-text search as a wider net
    url = _wiki_search_then_summary(f"{name} {city}".strip())
    if url:
        _cache.set(key, url)
        return url

    # Last resort — Unsplash keyword. We cache this too so the home feed is
    # consistent across reloads.
    url = _unsplash_fallback(category, name, city)
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
