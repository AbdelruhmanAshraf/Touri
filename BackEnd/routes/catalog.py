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

# ── Governorate → nearby cities proximity map ─────────────────────────────────
# Maps each Egyptian governorate label (as sent by the frontend, English part
# before the first space or parenthesis) to an ordered list of city keyword
# slugs that should be treated as "nearby".  The first entry is the primary
# city; subsequent entries are adjacent governorates ordered by proximity.
_GOVERNORATE_PROXIMITY: Dict[str, List[str]] = {
    "cairo":        ["cairo", "giza", "qalyubia"],
    "giza":         ["giza", "cairo", "fayyum", "beni suef"],
    "qalyubia":     ["qalyubia", "cairo", "gharbia", "sharqia"],
    "alexandria":   ["alexandria", "beheira", "matrouh"],
    "beheira":      ["beheira", "alexandria", "gharbia", "kafr el-sheikh"],
    "gharbia":      ["gharbia", "beheira", "monufia", "kafr el-sheikh"],
    "monufia":      ["monufia", "gharbia", "qalyubia", "cairo"],
    "dakahlia":     ["dakahlia", "sharqia", "damietta", "port said"],
    "damietta":     ["damietta", "dakahlia", "port said"],
    "sharqia":      ["sharqia", "qalyubia", "ismailia", "dakahlia"],
    "kafr el-sheikh": ["kafr el-sheikh", "gharbia", "beheira", "damietta"],
    "ismailia":     ["ismailia", "sharqia", "suez", "port said"],
    "port said":    ["port said", "ismailia", "damietta", "north sinai"],
    "suez":         ["suez", "ismailia", "south sinai", "cairo"],
    "north sinai":  ["north sinai", "ismailia", "port said", "south sinai"],
    "south sinai":  ["south sinai", "suez", "north sinai", "hurghada"],
    "fayyum":       ["fayyum", "giza", "beni suef"],
    "beni suef":    ["beni suef", "fayyum", "giza", "al-minya"],
    "al-minya":     ["al-minya", "beni suef", "asyut"],
    "asyut":        ["asyut", "al-minya", "sohag", "new valley"],
    "sohag":        ["sohag", "asyut", "qena"],
    "qena":         ["qena", "sohag", "luxor"],
    "luxor":        ["luxor", "qena", "aswan"],
    "aswan":        ["aswan", "luxor", "new valley"],
    "red sea":      ["hurghada", "red sea", "south sinai", "qena"],
    "hurghada":     ["hurghada", "red sea", "south sinai", "qena"],
    "matrouh":      ["matrouh", "alexandria", "new valley"],
    "new valley":   ["new valley", "asyut", "aswan", "matrouh"],
}


def _extract_governorate_key(city_param: str) -> str:
    """
    Turn the frontend label (e.g. 'Cairo (القاهرة)' or just 'cairo') into a
    lower-case English slug suitable for _GOVERNORATE_PROXIMITY lookup.
    """
    # Strip Arabic part: everything from '(' onward
    english = city_param.split("(")[0].strip().lower()
    # Also handle "Red Sea / Hurghada (…)" → "red sea"
    english = english.split("/")[0].strip()
    return english


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

    # Optional city personalisation: bubble items from the selected governorate
    # (and geographically adjacent ones) to the top using a tiered sort, and
    # also expose three explicit Phase-5 sections:
    #   - nearby_suggestions       — anything in adjacent governorates
    #   - localized_offers         — hot offers within the primary city only
    #   - hot_spots                — top-rated items in the primary city only
    if city:
        gov_key = _extract_governorate_key(city)
        nearby: List[str] = _GOVERNORATE_PROXIMITY.get(gov_key, [gov_key])
        primary = nearby[0] if nearby else gov_key
        adjacent = set(nearby[1:]) if len(nearby) > 1 else set()

        def _tier(card: Dict[str, Any]) -> int:
            card_city = (card.get("city") or "").lower()
            for rank, keyword in enumerate(nearby):
                if keyword in card_city:
                    return rank
            return len(nearby)

        def _proximity_first(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return sorted(cards, key=_tier)

        def _in_primary(card: Dict[str, Any]) -> bool:
            return primary in (card.get("city") or "").lower()

        def _in_adjacent(card: Dict[str, Any]) -> bool:
            cc = (card.get("city") or "").lower()
            return any(adj in cc for adj in adjacent)

        # Re-sort the existing buckets by proximity tier.
        payload = {k: _proximity_first(v) if isinstance(v, list) else v for k, v in payload.items()}

        # Build the three named sections from the catalog pool directly so
        # they survive even when an existing bucket is empty for this city.
        full_attractions = _cards(popular_attractions(min_rating=4.0, limit=80))
        full_offers      = _cards(hot_offers(limit=80))
        full_hotels      = _cards(featured_hotels(min_rating=4.0, limit=80))
        full_food        = _cards(local_food(min_rating=4.0, limit=80))

        nearby_pool = [c for c in (full_attractions + full_hotels + full_food) if _in_adjacent(c)]
        nearby_pool.sort(key=lambda c: c.get("rating") or 0, reverse=True)

        localized = [c for c in full_offers if _in_primary(c)]
        localized.sort(key=lambda c: c.get("rating") or 0, reverse=True)

        hot_spots_pool = [c for c in full_attractions if _in_primary(c)]
        hot_spots_pool.sort(key=lambda c: c.get("rating") or 0, reverse=True)

        payload["nearby_suggestions"]      = nearby_pool[:limit]
        payload["localized_offers"]        = localized[:limit]
        payload["hot_spots"]               = hot_spots_pool[:limit]

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
