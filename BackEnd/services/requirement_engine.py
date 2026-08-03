"""
Smart Requirement Collection Engine.

Determines which fields are missing before a trip plan can be generated,
cross-referencing:
  1. Onboarding persona (Firebase)
  2. Stored travel preferences (memory)
  3. Current user message
  4. Conversation history

Outputs: a list of ``StructuredQuestion`` objects for ONLY the missing fields.
Never asks for information already known.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from memory.user_persona import UserPersona
from models.question_schema import (
    QUESTION_REGISTRY,
    BilingualLabel,
    QuestionSet,
    StructuredQuestion,
)
from services.memory_service import TravelPreferences

logger = logging.getLogger(__name__)


# ── Field extraction from message text ──────────────────────────────────────
_DURATION_RE = re.compile(
    r"(\d+)\s*(?:day|days|يوم|أيام|ايام|night|nights|ليلة|ليالي|week|weeks|أسبوع|اسبوع)",
    re.IGNORECASE,
)

_DESTINATION_CITIES = {
    "cairo": "cairo", "القاهرة": "cairo",
    "alexandria": "alexandria", "الإسكندرية": "alexandria", "الاسكندرية": "alexandria",
    "luxor": "luxor", "الأقصر": "luxor", "الاقصر": "luxor",
    "aswan": "aswan", "أسوان": "aswan", "اسوان": "aswan",
    "hurghada": "hurghada", "الغردقة": "hurghada",
    "sharm": "sharm", "شرم": "sharm",
    "dahab": "dahab", "دهب": "dahab",
    "siwa": "siwa", "سيوة": "siwa",
    "fayoum": "fayoum", "الفيوم": "fayoum",
    "giza": "giza", "الجيزة": "giza",
    "red sea": "hurghada", "البحر الأحمر": "hurghada",
    "marsa alam": "marsa_alam", "مرسى علم": "marsa_alam",
}

_BUDGET_KEYWORDS = {
    "economy": "economy", "اقتصادي": "economy", "cheap": "economy",
    "رخيص": "economy", "budget": "economy",
    "mid-range": "mid_range", "moderate": "mid_range", "متوسط": "mid_range",
    "luxury": "luxury", "فاخر": "luxury", "premium": "luxury",
}

_PARTY_RE = re.compile(
    r"(\d+)\s*(?:people|person|persons|travellers|travelers|مسافر|شخص|أشخاص|اشخاص)",
    re.IGNORECASE,
)
_SOLO_RE = re.compile(r"\b(solo|alone|وحد|فرد|بمفرد)\b", re.IGNORECASE)
_COUPLE_RE = re.compile(r"\b(couple|زوج|ثنائي)\b", re.IGNORECASE)
_FAMILY_RE = re.compile(r"\b(family|عائلة|عائلت)\b", re.IGNORECASE)


class _ExtractedFields:
    """Fields extracted from the current message + history."""
    destination: Optional[str] = None
    duration: Optional[int] = None
    budget: Optional[str] = None
    party_size: Optional[int] = None
    trip_type: Optional[str] = None
    transportation: Optional[str] = None
    hotel_style: Optional[str] = None


def _extract_from_message(message: str) -> _ExtractedFields:
    """Extract structured fields from a user message."""
    result = _ExtractedFields()
    msg_lower = message.lower()

    # Destination
    for kw, city_id in _DESTINATION_CITIES.items():
        if kw.lower() in msg_lower:
            result.destination = city_id
            break

    # Duration
    m = _DURATION_RE.search(message)
    if m:
        result.duration = int(m.group(1))
    elif re.search(r"\b(week|أسبوع|اسبوع)\b", message, re.IGNORECASE):
        result.duration = 7

    # Budget
    for kw, val in _BUDGET_KEYWORDS.items():
        if kw in msg_lower:
            result.budget = val
            break

    # Party size
    m = _PARTY_RE.search(message)
    if m:
        result.party_size = int(m.group(1))
    elif _SOLO_RE.search(message):
        result.party_size = 1
    elif _COUPLE_RE.search(message):
        result.party_size = 2
    elif _FAMILY_RE.search(message):
        result.party_size = 4

    return result


def _extract_from_history(history: List[Dict[str, str]]) -> _ExtractedFields:
    """Scan chat history for any previously mentioned fields."""
    combined = _ExtractedFields()
    for msg in history:
        if msg.get("role") == "user":
            extracted = _extract_from_message(msg.get("content", ""))
            if extracted.destination and not combined.destination:
                combined.destination = extracted.destination
            if extracted.duration and not combined.duration:
                combined.duration = extracted.duration
            if extracted.budget and not combined.budget:
                combined.budget = extracted.budget
            if extracted.party_size and not combined.party_size:
                combined.party_size = extracted.party_size
    return combined


# ── Core logic: determine missing fields ────────────────────────────────────
def detect_missing_fields(
    *,
    message: str,
    persona: Optional[UserPersona] = None,
    travel_prefs: Optional[TravelPreferences] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    intent: str = "trip_planning",
    known_fields: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Return a list of missing field names required for the given intent.

    Cross-references:
      - Current message text
      - Onboarding persona
      - Stored travel preferences
      - Chat history

    Only fields actually needed for the intent are checked.
    """
    if intent not in ("trip_planning", "budget_query"):
        return []

    # Gather known fields from all sources
    msg_fields = _extract_from_message(message)
    hist_fields = _extract_from_history(chat_history or [])
    enforcer_known = known_fields or {}

    # Check each required field
    known: Set[str] = set()

    # Seed from memory enforcer (authoritative)
    for field in enforcer_known:
        if field == "trip_duration":
            known.add("duration")
        else:
            known.add(field)

    # Destination
    if (
        msg_fields.destination
        or hist_fields.destination
        or (persona and persona.preferred_destination)
        or (travel_prefs and travel_prefs.selected_cities)
    ):
        known.add("destination")

    # Duration (always required, cannot come from persona)
    if msg_fields.duration or hist_fields.duration or (travel_prefs and travel_prefs.trip_duration):
        known.add("duration")

    # Budget
    if (
        msg_fields.budget
        or hist_fields.budget
        or (persona and persona.budget_bracket)
        or (travel_prefs and travel_prefs.budget_preferences)
    ):
        known.add("budget")

    # Party size
    if (
        msg_fields.party_size
        or hist_fields.party_size
        or (persona and persona.party_size and persona.party_size > 0)
        or (travel_prefs and travel_prefs.family_size)
    ):
        known.add("party_size")

    # Define required fields per intent
    # Budget and party_size are always available from persona — only ask for
    # destination and duration which must come from the conversation.
    required_for_plan = {"destination", "duration"}
    required_for_budget = {"destination", "duration"}

    if intent == "trip_planning":
        required = required_for_plan
    else:
        required = required_for_budget

    missing = sorted(required - known)
    return missing


# ── Build structured questions for missing fields ───────────────────────────
def build_questions_for_gaps(
    gaps: List[str],
    language: str = "en",
    persona: Optional[UserPersona] = None,
    message: str = "",
) -> Optional[QuestionSet]:
    """
    Build a ``QuestionSet`` containing structured questions ONLY for missing
    fields. Returns None if no gaps.
    """
    if not gaps:
        return None

    questions: List[StructuredQuestion] = []
    for field in gaps:
        q = QUESTION_REGISTRY.get(field)
        if q:
            questions.append(q)

    if not questions:
        return None

    # Build a personalised intro
    name = ""
    if persona:
        name = " ".join(filter(None, [persona.first_name, persona.last_name])).strip()

    if language == "ar":
        greeting = f"أهلاً {name}!" if name else "أهلاً!"
        intro = f"{greeting} أحتاج بعض التفاصيل لأعد لك خطة مثالية."
    else:
        greeting = f"Hey {name}!" if name else "Hey there!"
        intro = f"{greeting} I'd love to help plan your trip. Just need a few details."

    return QuestionSet(
        questions=questions,
        intro_text=BilingualLabel(en=intro if language == "en" else "", ar=intro if language == "ar" else ""),
        remaining_fields=len(gaps),
    )


__all__ = [
    "detect_missing_fields",
    "build_questions_for_gaps",
]
