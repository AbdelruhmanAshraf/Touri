"""
Catalog routes — REST API that feeds the mobile home, place sheet, and search.

Endpoints
---------
GET  /api/catalog/home               curated home bundle (events, offers, etc.)
GET  /api/catalog/place/{type}/{id}  full detail for a single entity
GET  /api/catalog/search             keyword search across all domains
GET  /api/catalog/categories         distinct cities / cuisines / etc.

All responses are JSON-serialisable ``CatalogItem.to_dict`` / ``to_card``
payloads. Images for non-attraction entities are resolved lazily through
``tools.image_resolver`` (Wikipedia + Unsplash fallback, cached on disk).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from data.catalog import (
    by_id,
    by_type,
    best_now,
    categories as catalog_categories,
    featured_hotels,
    hot_offers,
    local_food,
    off_peak_picks,
    popular_attractions,
    search as catalog_search,
    upcoming_events,
)
from tools.image_resolver import prefetch_for_items, resolve_image

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catalog", tags=["catalog"])


# ── Helpers ───────────────────────────────────────────────────────────────────
def _enrich(item) -> dict:
    """Ensure every item has at least one image before returning."""
    if not item.image_urls:
        try:
            url = resolve_image(category=item.type, name=item.name, city=item.city)
            if url:
                item.image_urls = [url]
        except Exception as exc:  # noqa: BLE001
            logger.debug("[catalog] image resolve failed for %s: %s", item.name, exc)
    return item


def _cards(items) -> List[Dict[str, Any]]:
    return [_enrich(it).to_card() for it in items]


# ── Home bundle ───────────────────────────────────────────────────────────────
@router.get("/home")
async def home(
    city: Optional[str] = Query(default=None, description="Optional city filter for personalisation"),
    limit: int = Query(default=10, ge=1, le=20),
) -> Dict[str, Any]:
    """Curated home feed driven by current month, ratings, and price."""

    # Pre-warm images for the non-attraction sections so the frontend
    # doesn't hit the cold-cache spike on first render.
    offers_pool = hot_offers(limit=limit)
    events_pool = upcoming_events(limit=limit)
    prefetch_for_items(events_pool + offers_pool, max_items=2 * limit)

    payload = {
        "events": _cards(events_pool),
        "best_now": _cards(best_now(limit=limit)),
        "offers": _cards(offers_pool),
        "off_peak": _cards(off_peak_picks(limit=limit)),
        "popular": _cards(popular_attractions(limit=limit)),
        "featured_hotels": _cards(featured_hotels(limit=limit)),
        "local_food": _cards(local_food(limit=limit)),
    }

    # Optional city personalisation: if the user has a preferred city,
    # bubble matching items to the top of every list.
    if city:
        target = city.lower().strip()

        def _city_first(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            matched = [c for c in cards if target in (c.get("city") or "").lower()]
            others = [c for c in cards if c not in matched]
            return matched + others

        payload = {k: _city_first(v) if isinstance(v, list) else v for k, v in payload.items()}

    payload["meta"] = {
        "total_attractions": len(by_type().get("attraction", [])),
        "total_hotels": len(by_type().get("hotel", [])),
        "total_restaurants": len(by_type().get("restaurant", [])),
        "total_events": len(by_type().get("event", [])),
        "total_transport": len(by_type().get("transport", [])),
        "total_medical": len(by_type().get("medical", [])),
    }
    return payload


# ── Single place detail ───────────────────────────────────────────────────────
@router.get("/place/{item_type}/{item_id}")
async def place(item_type: str, item_id: str) -> Dict[str, Any]:
    item = by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.type != item_type:
        raise HTTPException(status_code=404, detail="Item type mismatch")
    return _enrich(item).to_dict()


# ── Search ────────────────────────────────────────────────────────────────────
_ALLOWED_TYPES = {
    "all", "attraction", "hotel", "restaurant", "transport",
    "flight", "event", "medical",
}


@router.get("/search")
async def search_endpoint(
    q: str = Query(..., min_length=1),
    type: str = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    t = type.lower().strip()
    if t not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported type filter: {type}")
    type_filter = None if t == "all" else t
    items = catalog_search(q, type_filter=type_filter, limit=limit)
    return {"query": q, "type": type, "results": _cards(items), "count": len(items)}


# ── Categories ────────────────────────────────────────────────────────────────
@router.get("/categories")
async def categories_endpoint() -> Dict[str, Any]:
    return catalog_categories()


# ── Image resolver passthrough (debug helper) ─────────────────────────────────
@router.get("/image")
async def image_endpoint(
    category: str = Query(..., description="hotel | restaurant | event | medical | …"),
    name: str = Query(..., min_length=1),
    city: str = Query(default=""),
) -> Dict[str, str]:
    url = resolve_image(category=category, name=name, city=city)
    return {"url": url}


__all__ = ["router"]
