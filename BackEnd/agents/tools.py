"""
Touri Function-Calling tools — AI agentic upgrades.

These are the four "first-class" tools agents may invoke during a chat turn
to fetch real, grounded data instead of hallucinating answers:

    1. get_live_weather(city, date)
    2. query_local_catalog(category, price_bracket, restrictions)
    3. search_live_flights_and_rates(origin, destination)
    4. update_user_persona_record(field, value)

The tool schemas are declared in standard OpenAPI schema format and
the Python implementations dispatch through ``execute_tool``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Tool schemas (OpenAPI function definitions) ───────────────────────────
TOOL_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "get_live_weather",
        "description": (
            "Fetch current weather and short-term outlook for an Egyptian city "
            "or governorate. Use whenever the user asks about clothing, "
            "packing, outdoor activities, or 'is it hot/cold next week'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Egyptian city or governorate, e.g. 'Cairo', 'Luxor', 'Hurghada'.",
                },
                "date": {
                    "type": "string",
                    "description": "ISO 8601 date or relative phrase ('today', 'next week'). Optional.",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "query_local_catalog",
        "description": (
            "Look up curated Touri entries (3,723 Egypt items) — hotels, "
            "restaurants, attractions, medical centers, events. Use whenever "
            "the user asks for a verified recommendation matching specific "
            "criteria like cuisine, dietary needs, or price bracket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "hotel", "restaurant", "attraction",
                        "medical", "event", "transport", "flight",
                    ],
                    "description": "Catalog domain to query.",
                },
                "city": {
                    "type": "string",
                    "description": "Optional governorate filter (e.g. 'Cairo').",
                },
                "price_bracket": {
                    "type": "string",
                    "enum": ["economy", "mid_range", "luxury"],
                    "description": "Optional budget tier.",
                },
                "restrictions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional dietary / amenity tags (e.g. ['halal','vegetarian']).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 5).",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "search_live_flights_and_rates",
        "description": (
            "Use the Tavily live web-search tool to find current flight "
            "options, average ticket prices, or currency conversion rates. "
            "Trigger whenever the user asks about today's prices, real-time "
            "FX, or flight availability."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Departure city / airport / country.",
                },
                "destination": {
                    "type": "string",
                    "description": "Arrival city / airport / country.",
                },
                "query": {
                    "type": "string",
                    "description": "Free-form fallback query if origin+dest aren't enough.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "update_user_persona_record",
        "description": (
            "Patch a single field on the active user's Touri persona "
            "record (Firestore). Use whenever the user mentions a NEW "
            "preference (budget changed, party size changed, dietary needs "
            "changed). The value is stored verbatim — quoting normal "
            "language is fine."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": [
                        "preferred_destination",
                        "tourism_type",
                        "party_size",
                        "budget_bracket",
                        "dietary",
                        "language_preference",
                    ],
                    "description": "Persona field to update.",
                },
                "value": {
                    "type": "string",
                    "description": "New value (string form; integers will be parsed).",
                },
            },
            "required": ["field", "value"],
        },
    },
]


# ── Implementations ───────────────────────────────────────────────────────────
async def _impl_weather(city: str, date: Optional[str] = None) -> Dict[str, Any]:
    from tools import weather as wtool  # local import to avoid cycles

    try:
        text = wtool.get_weather(city)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "city": city, "date": date or "today", "summary": text}


async def _impl_catalog(
    category: str,
    city: Optional[str] = None,
    price_bracket: Optional[str] = None,
    restrictions: Optional[List[str]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    from data import catalog as cat

    try:
        bucket = cat.by_type().get(category, [])
        results = []
        norm_city = (city or "").lower().strip()
        norm_restr = [r.lower() for r in (restrictions or [])]
        for item in bucket:
            if norm_city and norm_city not in item.city.lower():
                continue
            if price_bracket and (item.price_category or "").lower() and \
               price_bracket not in item.price_category.lower():
                continue
            if norm_restr:
                pool = [d.lower() for d in (item.dietary or [])] + \
                       [a.lower() for a in (item.amenities or [])]
                if not all(any(r in p for p in pool) for r in norm_restr):
                    continue
            results.append({
                "id": item.id,
                "name": item.name,
                "city": item.city,
                "rating": item.rating,
                "price_egp": item.price_egp,
                "price_usd": item.price_usd,
                "subtype": item.subtype,
            })
            if len(results) >= max(1, min(limit, 10)):
                break
        return {"ok": True, "category": category, "count": len(results), "results": results}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def _impl_flights(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    from tools import web_search as wsearch

    q = query or " ".join(filter(None, [
        "live flight prices", origin and f"from {origin}", destination and f"to {destination}",
    ]))
    if not q.strip():
        return {"ok": False, "error": "missing origin/destination/query"}
    try:
        result = await wsearch.search_live_travel_data(q, max_results=5)
        # ``result`` is a dataclass — coerce to a plain dict for tool reply.
        if hasattr(result, "__dict__"):
            payload = {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
        else:
            payload = {"raw": str(result)}
        return {"ok": True, "query": q, "result": payload}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def _impl_persona_update(
    field: str, value: str, *, user_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not user_id:
        return {"ok": False, "error": "user_id missing in tool context"}

    from memory.user_persona import (
        BudgetBracket, TourismType, update_persona_fields,
    )

    updates: Dict[str, Any] = {}
    f = field.strip().lower()
    v = (value or "").strip()
    try:
        if f == "preferred_destination":
            updates["preferred_destination"] = v
        elif f == "tourism_type":
            updates["tourism_type"] = TourismType(v.lower())
        elif f == "party_size":
            updates["party_size"] = int(v)
        elif f == "budget_bracket":
            updates["budget_bracket"] = BudgetBracket(v.lower())
        elif f in ("dietary", "language_preference"):
            # Free-form extras
            updates["extras"] = {f: v}
        else:
            return {"ok": False, "error": f"unsupported field: {field}"}
        merged = await update_persona_fields(user_id, updates)
        return {
            "ok": True,
            "field": field,
            "value": value,
            "persona": {
                "preferred_destination": merged.preferred_destination,
                "tourism_type": merged.tourism_type.value,
                "party_size": merged.party_size,
                "budget_bracket": merged.budget_bracket.value,
                "extras": merged.extras,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[tools] persona update failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ── Dispatch table ────────────────────────────────────────────────────────────
_DISPATCH: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "get_live_weather": _impl_weather,
    "query_local_catalog": _impl_catalog,
    "search_live_flights_and_rates": _impl_flights,
    "update_user_persona_record": _impl_persona_update,
}


async def execute_tool(
    name: str, args: Dict[str, Any], *, user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one tool by name with the given JSON-like args dict."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        if name == "update_user_persona_record":
            return await fn(**args, user_id=user_id)
        return await fn(**args)
    except TypeError as exc:
        return {"ok": False, "error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[tools] %s failed", name)
        return {"ok": False, "error": str(exc)}


__all__ = ["TOOL_DECLARATIONS", "execute_tool"]
