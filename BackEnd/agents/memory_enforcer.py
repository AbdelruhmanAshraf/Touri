"""
Memory Enforcer — LangGraph node.

Runs after the memory_manager node, before the router.
Reads the fully-loaded state (persona + travel_preferences + itinerary)
and builds two dicts:

  known_fields:   {field: value}  — agent MUST NOT re-ask these
  missing_fields: [field, ...]    — agent MAY ask for these

All downstream nodes (router, planner, budget) receive these so their
prompts include a hard "do not re-ask" instruction for every known field.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.state import AgentState, make_step
from agents.llm import t

logger = logging.getLogger(__name__)

# The canonical set of trip-planning fields we track.
_ALL_FIELDS = [
    "destination",
    "trip_duration",
    "budget",
    "party_size",
    "tourism_type",
]


def _extract_known(state: AgentState) -> Dict[str, Any]:
    """
    Harvest field values from every available source (persona,
    travel_preferences, conversation_state, last itinerary).
    Returns only fields that have a definite non-null value.
    """
    known: Dict[str, Any] = {}
    persona = state.get("user_persona")
    prefs = state.get("travel_preferences") or {}
    conv = state.get("conversation_state") or {}
    itinerary = state.get("itinerary") or {}

    # ── destination ──────────────────────────────────────────────────────────
    dest = (
        (persona.preferred_destination if persona else None)
        or prefs.get("selected_cities", [None])[0]
        or itinerary.get("city")
        or None
    )
    if dest:
        known["destination"] = dest

    # ── trip_duration ─────────────────────────────────────────────────────────
    dur = (
        prefs.get("trip_duration")
        or itinerary.get("duration")
        or None
    )
    if dur:
        known["trip_duration"] = int(dur)

    # ── budget ────────────────────────────────────────────────────────────────
    budget_val = (
        (persona.budget_bracket.value if persona and persona.budget_bracket else None)
        or prefs.get("budget_preferences")
        or None
    )
    if budget_val:
        known["budget"] = budget_val

    # ── party_size ────────────────────────────────────────────────────────────
    party = (
        (persona.party_size if persona and persona.party_size else None)
        or prefs.get("family_size")
        or None
    )
    if party and int(party) > 0:
        known["party_size"] = int(party)

    # ── tourism_type ──────────────────────────────────────────────────────────
    ttype = (
        (persona.tourism_type.value if persona and persona.tourism_type else None)
        or None
    )
    if ttype:
        known["tourism_type"] = ttype

    # ── conversation_state completed requirements ─────────────────────────────
    completed = conv.get("completed_requirements") or []
    for field in completed:
        if field not in known:
            known[field] = True  # We know it's satisfied even without the value

    return known


def _compute_missing(known: Dict[str, Any]) -> List[str]:
    return [f for f in _ALL_FIELDS if f not in known]


def build_memory_enforcement_prompt(known: Dict[str, Any], missing: List[str], language: str = "en") -> str:
    """
    Returns a compact prompt fragment that all downstream agents append
    to their system prompts to enforce the "do not re-ask" rule.
    """
    if not known and not missing:
        return ""

    if language == "ar":
        lines = []
        if known:
            known_str = ", ".join(f"{k}={v}" for k, v in known.items())
            lines.append(f"المعلومات المعروفة (لا تسأل عنها مجدداً): {known_str}")
        if missing:
            miss_str = ", ".join(missing)
            lines.append(f"المعلومات الناقصة (اسأل عن هذه فقط إذا لزم): {miss_str}")
        return "\n".join(lines)

    lines = []
    if known:
        known_str = ", ".join(f"{k}={v}" for k, v in known.items())
        lines.append(f"KNOWN (DO NOT re-ask the user for these): {known_str}")
    if missing:
        miss_str = ", ".join(missing)
        lines.append(f"MISSING (may ask for only these if needed): {miss_str}")
    return "\n".join(lines)


async def enforce_memory(state: AgentState) -> AgentState:
    """LangGraph node: populate known_fields and missing_fields in state."""
    language = state.get("language", "en")

    known = _extract_known(state)
    missing = _compute_missing(known)

    state["known_fields"] = known
    state["missing_fields"] = missing

    if "agent_trace" not in state:
        state["agent_trace"] = []
    state["agent_trace"].append(
        make_step(
            agent="Memory Enforcer",
            action=t(language, "Enforce memory constraints", "تطبيق قيود الذاكرة"),
            tool="state",
            reasoning=t(
                language,
                f"Known fields: {list(known.keys())}. Missing: {missing}. "
                "Downstream agents will not re-ask for known information.",
                f"الحقول المعروفة: {list(known.keys())}. الناقصة: {missing}. "
                "الوكلاء لن يعيدون السؤال عن المعلومات المعروفة.",
            ),
            result=f"known={len(known)}, missing={len(missing)}",
        )
    )

    return state


__all__ = ["enforce_memory", "build_memory_enforcement_prompt"]
