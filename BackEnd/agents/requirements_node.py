"""
Requirements Node — smart slot-filling gate before the planner/budget agents.

Sits between the router and the terminal agents. If required slots are still
missing it asks 1-2 structured questions (rendered as chips by the frontend)
and returns intent=needs_info. When all slots are known it forwards the state
to the correct downstream agent without touching response_text.

Slot set (10 fields, matches REQUIRED_FIELDS in conversation_state.py):
  destination, duration, budget, party_size, trip_type,
  transportation, hotel_style, activities, dietary, start_date

Skip logic:
  - persona.preferred_destination  → fills destination
  - persona.party_size             → fills party_size
  - persona.budget_bracket         → fills budget
  - persona.tourism_type           → fills trip_type
  - travel_preferences fields      → fill matching slots
  - prior chat_history answers     → scanned by requirement_engine
"""

from __future__ import annotations

import logging
from typing import List

from agents.state import AgentState, Intent, make_step
from agents.llm import t
from models.question_schema import QUESTION_REGISTRY, QuestionSet, BilingualLabel
from services.requirement_engine import detect_missing_fields, build_questions_for_gaps
from services.memory_service import TravelPreferences

logger = logging.getLogger(__name__)

# Maximum fields to ask about in a single turn (keeps UI clean)
_MAX_QUESTIONS_PER_TURN = 2

# Fields that MUST be present before we dispatch to planner/budget
_CRITICAL = frozenset({"destination", "duration", "budget", "party_size"})

# Fields that are nice-to-have but not blocking
_OPTIONAL = frozenset({"trip_type", "transportation", "hotel_style", "activities", "dietary", "start_date"})


async def gather_requirements(state: AgentState) -> AgentState:
    """
    LangGraph node: check slots, ask structured questions if needed,
    or pass through to the next agent when ready.

    Sets state['intent'] = 'needs_info' and populates structured_questions
    when gaps exist; otherwise leaves intent unchanged so the existing
    conditional edge routes to the correct specialist.
    """
    language = state.get("language", "en")
    message = state.get("user_message", "")
    intent: Intent = state.get("intent", "general")
    persona = state.get("user_persona")

    # Only intercept planning / budget intents
    if intent not in ("trip_planning", "budget_query"):
        return state

    # Resolve travel_preferences from state
    travel_prefs = None
    raw_prefs = state.get("travel_preferences", {})
    if raw_prefs:
        try:
            travel_prefs = TravelPreferences(
                **{k: v for k, v in raw_prefs.items() if k in TravelPreferences.model_fields}
            )
        except Exception:
            travel_prefs = None

    # Detect missing fields using the existing requirement engine
    all_gaps: List[str] = detect_missing_fields(
        message=message,
        persona=persona,
        travel_prefs=travel_prefs,
        chat_history=state.get("chat_history", []),
        intent=intent,
    )

    # Split into critical vs optional gaps
    critical_gaps = [g for g in all_gaps if g in _CRITICAL]
    optional_gaps = [g for g in all_gaps if g in _OPTIONAL]

    # If no critical gaps → dispatch immediately; skip optional for now
    if not critical_gaps:
        state["agent_trace"].append(
            make_step(
                agent="Requirements Node",
                action=t(language, "Requirements satisfied", "المتطلبات مكتملة"),
                tool="requirement_engine",
                reasoning=t(
                    language,
                    f"All critical slots filled. Optional gaps: {optional_gaps or 'none'}. "
                    f"Forwarding to {intent} agent.",
                    f"جميع الحقول الأساسية مكتملة. الحقول الاختيارية الناقصة: {optional_gaps or 'لا يوجد'}. "
                    f"يتم التحويل إلى وكيل {intent}.",
                ),
                result=f"critical_gaps=0, optional_gaps={len(optional_gaps)}",
            )
        )
        return state

    # Prioritise critical gaps; ask at most _MAX_QUESTIONS_PER_TURN
    gaps_to_ask = (critical_gaps + optional_gaps)[:_MAX_QUESTIONS_PER_TURN]

    # Build structured questions (chip UI)
    question_set = build_questions_for_gaps(gaps_to_ask, language, persona, message)
    if question_set:
        state["structured_questions"] = question_set.model_dump()

    # Build a friendly follow-up intro
    name = ""
    if persona:
        name = " ".join(filter(None, [persona.first_name, persona.last_name])).strip()

    if language == "ar":
        greeting = f"أهلاً {name}!" if name else "أهلاً!"
        items = []
        for gap in gaps_to_ask:
            q = QUESTION_REGISTRY.get(gap)
            if q:
                items.append(f"- {q.question.ar}")
        intro = (
            f"{greeting} لأتمكن من إعداد خطة رحلة مثالية لك، "
            f"أحتاج لبعض المعلومات الإضافية:"
        )
        state["response_text"] = f"{intro}\n" + "\n".join(items) if items else intro
    else:
        greeting = f"Hey {name}!" if name else "Hey there!"
        items = []
        for gap in gaps_to_ask:
            q = QUESTION_REGISTRY.get(gap)
            if q:
                items.append(f"- {q.question.en}")
        intro = (
            f"{greeting} To build the perfect itinerary for you, "
            f"I need a couple more details:"
        )
        state["response_text"] = f"{intro}\n" + "\n".join(items) if items else intro

    # Update conversation requirements tracking
    conv_state = state.get("conversation_state")
    if conv_state and isinstance(conv_state, dict):
        conv_state["missing_requirements"] = sorted(all_gaps)
        state["conversation_state"] = conv_state

    remaining = max(0, len(all_gaps) - len(gaps_to_ask))
    state["requirements_status"] = {
        "missing": all_gaps,
        "asking": gaps_to_ask,
        "remaining_after": remaining,
    }

    state["intent"] = "needs_info"
    state["active_agent"] = "Touri Assistant"
    state["suggestions"] = _build_quick_replies(gaps_to_ask, language)

    state["agent_trace"].append(
        make_step(
            agent="Requirements Node",
            action=t(language, "Gather requirements", "جمع المتطلبات"),
            tool="requirement_engine",
            reasoning=t(
                language,
                f"Missing critical fields: {critical_gaps}. "
                f"Asking {len(gaps_to_ask)} structured question(s) before dispatching.",
                f"الحقول الأساسية الناقصة: {critical_gaps}. "
                f"طرح {len(gaps_to_ask)} سؤال/أسئلة مهيكلة قبل التحويل.",
            ),
            result=f"gaps={all_gaps}, asking={gaps_to_ask}",
        )
    )
    return state


def _build_quick_replies(gaps: List[str], language: str) -> List[str]:
    """Return 3 contextual suggestion chips based on the first gap."""
    if not gaps:
        return []
    first = gaps[0]
    if language == "ar":
        _ar = {
            "destination": ["القاهرة", "الإسكندرية", "الأقصر وأسوان"],
            "duration": ["3 أيام", "5 أيام", "أسبوع كامل"],
            "budget": ["اقتصادي", "متوسط", "فاخر"],
            "party_size": ["فردي", "ثنائي", "عائلة (4 أفراد)"],
            "trip_type": ["ترفيهية", "تاريخية", "استرخاء"],
            "transportation": ["أوبر", "مواصلات عامة", "سيارة مستأجرة"],
        }
        return _ar.get(first, ["القاهرة", "3 أيام", "متوسط"])
    _en = {
        "destination": ["Cairo", "Alexandria", "Luxor & Aswan"],
        "duration": ["3 days", "5 days", "1 week"],
        "budget": ["Economy", "Mid-range", "Luxury"],
        "party_size": ["Solo", "Couple", "Family (4)"],
        "trip_type": ["Leisure", "Historical", "Relaxation"],
        "transportation": ["Uber", "Public transport", "Rental car"],
    }
    return _en.get(first, ["Cairo", "3 days", "Mid-range"])


__all__ = ["gather_requirements"]
