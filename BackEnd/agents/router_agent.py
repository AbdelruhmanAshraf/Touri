"""
Router agent: persona load + bilingual intent detection + smart follow-up.

Ingests the text query + current user's Firestore UserPersona (including
the new ``extras.allergies`` field) and categorizes intent into:
    trip_planning | budget_query | local_info | general | needs_info

When intent is trip_planning or budget_query but critical info (like duration)
is missing, the router sets intent to ``needs_info`` and generates a
conversational follow-up question instead of dispatching immediately.
It never re-asks what's already known from the persona or the message.

Output: ``state['intent']``, ``state['active_agent']``, ``state['user_persona']``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import FAST_MODEL, get_llm, lang_directive, t, safe_extract_text, detect_language
from agents.state import AgentState, Intent, make_step
from memory.firebase_client import is_ready as firebase_ready
from memory.user_persona import UserPersona, get_or_create_persona
from middleware.prompt_firewall import analyze_prompt
from services.memory_service import TravelPreferences
from services.requirement_engine import detect_missing_fields, build_questions_for_gaps
from services.conversation_state import REQUIRED_FIELDS
from services.state_machine import StateMachine, ConversationState

logger = logging.getLogger(__name__)


# ── Heuristic intent detection (fast path before LLM) ─────────────────────────
_KW_BUDGET = re.compile(
    r"\b(budget|cost|price|how much|cheap|expensive|afford|ميزانية|تكلفة|سعر|كم|رخيص|غالي)\b",
    re.IGNORECASE,
)
_KW_PLAN = re.compile(
    r"\b(plan|itinerary|trip|day|schedule|visit|tour|خطة|برنامج|رحلة|جدول|زيارة)\b",
    re.IGNORECASE,
)
_KW_LOCAL = re.compile(
    r"\b(restaurant|food|eat|cafe|event|hidden|local|spot|مطعم|طعام|مقهى|فعالية|محلي|مكان)\b",
    re.IGNORECASE,
)


def _heuristic_intent(message: str) -> Optional[Intent]:
    if _KW_BUDGET.search(message):
        return "budget_query"
    if _KW_PLAN.search(message):
        return "trip_planning"
    if _KW_LOCAL.search(message):
        return "local_info"
    return None


# ── LLM intent detection (fallback) ───────────────────────────────────────────
_INTENT_PROMPT_EN = """\
You classify a traveller's chat message into exactly ONE intent for our routing
graph. Return JSON only: {{"intent": "<one of: trip_planning | budget_query | local_info | general>"}}.

Definitions:
- trip_planning: user wants an itinerary, day-by-day plan, route, multi-stop tour.
- budget_query: user asks about cost, price, savings, exchange rate, total spend.
- local_info: user asks for restaurants, dining, cafes, events, hidden gems, attractions.
- general: small talk, greetings, anything not above.

User persona context:
{persona_context}

Message:
{message}
"""

_INTENT_PROMPT_AR = """\
صنّف رسالة المسافر إلى نية واحدة فقط من النوايا التالية. أعد JSON فقط:
{{"intent": "<trip_planning | budget_query | local_info | general>"}}

التعريفات:
- trip_planning: المستخدم يريد خطة رحلة أو جدول يومي.
- budget_query: سؤال عن السعر، التكلفة، الميزانية، سعر الصرف.
- local_info: سؤال عن المطاعم، الفعاليات، الأماكن المحلية أو الخفية.
- general: محادثة عامة أو لا تنطبق الفئات السابقة.

سياق ملف المستخدم:
{persona_context}

الرسالة:
{message}
"""


def _build_persona_context(persona: Optional[UserPersona]) -> str:
    if not persona:
        return "(no persona on file)"
    parts = [
        f"tourism_type={persona.tourism_type.value}",
        f"party_size={persona.party_size}",
        f"budget={persona.budget_bracket.value}",
        f"destination={persona.preferred_destination or 'unspecified'}",
    ]
    if persona.extras:
        dietary = persona.extras.get("dietary_restrictions") or []
        allergies = persona.extras.get("allergies") or []
        if dietary:
            parts.append(f"dietary={','.join(str(d) for d in dietary)}")
        if allergies:
            parts.append(f"allergies={','.join(str(a) for a in allergies)}")
    return " | ".join(parts)


async def _llm_intent(message: str, language: str, persona: Optional[UserPersona] = None) -> Intent:
    llm = get_llm(model=FAST_MODEL, temperature=0.0, streaming=False)
    persona_context = _build_persona_context(persona)
    prompt = (_INTENT_PROMPT_AR if language == "ar" else _INTENT_PROMPT_EN).format(
        message=message,
        persona_context=persona_context,
    )
    try:
        resp = await llm.ainvoke(
            [SystemMessage(content=lang_directive(language)), HumanMessage(content=prompt)]
        )
        raw = safe_extract_text(resp.content)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group(0)) if match else {}
        candidate = str(data.get("intent", "")).strip().lower()
        if candidate in ("trip_planning", "budget_query", "local_info", "general"):
            return candidate  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[router] LLM intent detection failed: %s", exc)
    return "general"


# ── Persona loader ────────────────────────────────────────────────────────────
async def _load_persona(user_id: str) -> Optional[UserPersona]:
    if not firebase_ready():
        logger.debug("[router] Firebase not ready — skipping persona load")
        return None
    try:
        return await get_or_create_persona(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[router] persona load failed: %s", exc)
        return None


# ── Smart follow-up: gap detection ───────────────────────────────────────────
_DURATION_RE = re.compile(
    r"(\d+)\s*(?:day|days|يوم|أيام|ايام|night|nights|ليلة|ليالي|week|weeks|أسبوع|اسبوع)",
    re.IGNORECASE,
)

_DESTINATION_CITIES = [
    "cairo", "alexandria", "luxor", "aswan", "hurghada", "sharm",
    "dahab", "marsa alam", "siwa", "fayoum", "giza", "red sea",
    "القاهرة", "الإسكندرية", "الاسكندرية", "الأقصر", "الاقصر",
    "أسوان", "اسوان", "الغردقة", "شرم", "دهب", "سيوة", "الفيوم",
    "الجيزة", "البحر الأحمر", "مرسى علم",
]


def _extract_destination_from_msg(message: str) -> Optional[str]:
    msg_lower = message.lower()
    for city in _DESTINATION_CITIES:
        if city.lower() in msg_lower:
            return city.title()
    return None


def _extract_duration_from_msg(message: str) -> Optional[int]:
    m = _DURATION_RE.search(message)
    if m:
        return int(m.group(1))
    if re.search(r"\b(week|أسبوع|اسبوع)\b", message, re.IGNORECASE):
        return 7
    return None


def _detect_gaps(
    message: str,
    persona: Optional[UserPersona],
    intent: Intent,
) -> List[str]:
    """Return a list of missing info keys for the given intent.

    Cross-references: message text, persona profile, and stored travel preferences.
    """
    if intent not in ("trip_planning", "budget_query"):
        return []

    gaps: List[str] = []

    has_destination = bool(
        _extract_destination_from_msg(message)
        or (persona and persona.preferred_destination)
    )
    has_duration = bool(_extract_duration_from_msg(message))
    has_budget = bool(persona and persona.budget_bracket)
    has_party = bool(persona and persona.party_size and persona.party_size > 0)

    if not has_destination:
        gaps.append("destination")
    if not has_duration:
        gaps.append("duration")

    return gaps


def _build_followup(
    gaps: List[str],
    language: str,
    persona: Optional[UserPersona],
    message: str,
) -> str:
    """Build a natural follow-up question covering missing fields."""
    dest_from_msg = _extract_destination_from_msg(message)
    dest = dest_from_msg or (persona.preferred_destination if persona else None) or ""

    name = ""
    if persona:
        name = " ".join(filter(None, [persona.first_name, persona.last_name])).strip()

    if language == "ar":
        greeting = f"أهلاً {name}!" if name else "أهلاً!"
        parts: List[str] = []
        if "destination" in gaps:
            parts.append("ما الوجهة التي تود زيارتها في مصر؟")
        if "duration" in gaps:
            if dest:
                parts.append(f"كم يوم تخطط لقضائها في {dest}؟")
            else:
                parts.append("كم يوم تخطط لقضائها؟")
        if "budget" in gaps:
            parts.append("ما مستوى الميزانية المفضل لديك؟ (اقتصادي، متوسط، أو فاخر)")
        if "party_size" in gaps:
            parts.append("كم عدد المسافرين؟")

        question_block = "\n".join(f"- {p}" for p in parts) if len(parts) > 1 else parts[0] if parts else ""
        intro = f"{greeting} أحتاج بعض التفاصيل لأعد لك خطة مثالية:"
        return f"{intro}\n{question_block}" if len(parts) > 1 else f"{intro}\n{question_block}"

    greeting = f"Hey {name}!" if name else "Hey there!"
    parts = []
    if "destination" in gaps:
        parts.append("Which city or region in Egypt are you thinking of visiting?")
    if "duration" in gaps:
        if dest:
            parts.append(f"How many days are you planning to spend in {dest}?")
        else:
            parts.append("How many days are you planning for the trip?")
    if "budget" in gaps:
        parts.append("What's your preferred budget level? (economy, mid-range, or luxury)")
    if "party_size" in gaps:
        parts.append("How many people will be traveling?")

    question_block = "\n".join(f"- {p}" for p in parts) if len(parts) > 1 else parts[0] if parts else ""
    intro = f"{greeting} I'd love to help plan your trip. Just need a couple of details:"
    return f"{intro}\n{question_block}" if len(parts) > 1 else f"{intro}\n{question_block}"


# ── Public node ───────────────────────────────────────────────────────────────
_AGENT_LABEL = {
    "trip_planning": "Travel Planner",
    "budget_query": "Budget Specialist",
    "local_info": "Local Concierge",
    "general": "Travel Planner",
    "needs_info": "Router",
    "fallback": "Travel Planner",
}

_AGENT_LABEL_AR = {
    "trip_planning": "وكيل التخطيط",
    "budget_query": "خبير الميزانية",
    "local_info": "الكونسيرج المحلي",
    "general": "وكيل التخطيط",
    "needs_info": "وكيل التوجيه",
    "fallback": "وكيل التخطيط",
}


async def route(state: AgentState) -> AgentState:
    """LangGraph node: enriches state with persona + intent + active_agent."""
    language = state.get("language", "en")
    message = state.get("user_message", "")
    user_id = state.get("user_id", "")

    # SECURITY: Prompt injection firewall — analyze and sanitize user input
    firewall_result = analyze_prompt(message)
    if firewall_result.blocked:
        state["intent"] = "general"
        state["active_agent"] = "Travel Planner"
        state["response_text"] = t(
            language,
            "I'm here to help you plan your Egypt trip! Could you rephrase your question about travel, budget, or local recommendations?",
            "أنا هنا لمساعدتك في التخطيط لرحلتك في مصر! هل يمكنك إعادة صياغة سؤالك حول السفر أو الميزانية أو التوصيات المحلية؟",
        )
        state["suggestions"] = [
            t(language, "Plan a trip to Cairo", "خطط رحلة للقاهرة"),
            t(language, "Best restaurants in Luxor", "أفضل المطاعم في الأقصر"),
            t(language, "Budget for 5 days in Egypt", "ميزانية 5 أيام في مصر"),
        ]
        state["agent_trace"].append(
            make_step(
                agent="Router",
                action=t(language, "Input validation", "التحقق من المدخلات"),
                tool="prompt_firewall",
                reasoning=t(
                    language,
                    "Input was flagged by security filters. Returning safe travel guidance.",
                    "تم تصنيف المدخلات بواسطة فلاتر الأمان. يتم إرجاع إرشادات سفر آمنة.",
                ),
                result="blocked",
            )
        )
        return state

    # Use sanitized message from firewall
    message = firewall_result.sanitized_text
    state["user_message"] = message

    # Auto-detect language from message content and override if mismatched
    detected = detect_language(message)
    if detected != language and message.strip():
        language = detected
        state["language"] = language

    # 1. Persona (including allergies from extras)
    persona = await _load_persona(user_id)
    state["user_persona"] = persona

    allergies_str = ""
    if persona and persona.extras:
        allergies = persona.extras.get("allergies") or []
        if allergies:
            allergies_str = ", ".join(str(a) for a in allergies)

    state["agent_trace"].append(
        make_step(
            agent="Router",
            action=t(language, "Load user persona", "تحميل بيانات المستخدم"),
            tool="firestore",
            reasoning=t(
                language,
                "Pulled persona to bias intent (tourism_type, budget, allergies, dietary).",
                "تم تحميل ملف المستخدم لتحسين فهم النية (نوع السياحة، الميزانية، الحساسية الغذائية).",
            ),
            result=(
                f"tourism_type={persona.tourism_type.value}, "
                f"party_size={persona.party_size}, "
                f"budget={persona.budget_bracket.value}"
                + (f", allergies=[{allergies_str}]" if allergies_str else "")
            )
            if persona
            else (None),
        )
    )

    # 2. Intent — try heuristics first, fall back to Gemma
    intent: Intent = _heuristic_intent(message) or await _llm_intent(message, language, persona)

    # 3. Persona override: if user is on Medical tourism and intent is generic,
    #    prefer trip planning so the planner can weave in healthcare facilities.
    if persona and persona.tourism_type.value == "medical" and intent == "general":
        intent = "trip_planning"
    # Apply logic from Phase 10 State Machine
    state_machine = StateMachine()
    current_state_str = state.get("conversation_state", {}).get("current_state", ConversationState.ONBOARDING.value) if state.get("conversation_state") else ConversationState.ONBOARDING.value
    current_sm_state = ConversationState(current_state_str)
    # 4. Smart follow-up: check for missing critical info using requirement engine
    #    Cross-references: persona, stored prefs, chat history, current message
    travel_prefs = None
    raw_prefs = state.get("travel_preferences", {})
    if raw_prefs:
        try:
            travel_prefs = TravelPreferences(**{k: v for k, v in raw_prefs.items() if k in TravelPreferences.model_fields})
        except Exception:
            travel_prefs = None

    gaps = detect_missing_fields(
        message=message,
        persona=persona,
        travel_prefs=travel_prefs,
        chat_history=state.get("chat_history", []),
        intent=intent,
    )

    # Update conversation state requirements tracking
    conv_state = state.get("conversation_state")
    if conv_state and isinstance(conv_state, dict):
        completed = set(conv_state.get("completed_requirements", []))
        all_fields = set(REQUIRED_FIELDS)
        gap_set = set(gaps) if gaps else set()
        known_fields = all_fields - gap_set
        completed.update(known_fields)
        conv_state["completed_requirements"] = sorted(completed)
        conv_state["missing_requirements"] = sorted(gap_set)
        state["conversation_state"] = conv_state
        pct = (len(completed) / len(REQUIRED_FIELDS) * 100) if REQUIRED_FIELDS else 0.0
        state["requirements_status"] = {
            "completed": sorted(completed),
            "missing": sorted(gap_set),
            "total": len(REQUIRED_FIELDS),
            "percentage": round(pct, 1),
        }

    if gaps:
        # Build structured questions for the frontend
        question_set = build_questions_for_gaps(gaps, language, persona, message)
        if question_set:
            state["structured_questions"] = question_set.model_dump()

        followup_text = _build_followup(gaps, language, persona, message)
        
        # State Machine Phase 10 Transition
        if state_machine.can_transition(current_sm_state, ConversationState.COLLECTING_REQUIREMENTS):
            if "conversation_state" not in state or not state["conversation_state"]:
                state["conversation_state"] = {}
            state["conversation_state"]["current_state"] = ConversationState.COLLECTING_REQUIREMENTS.value
            
        state["intent"] = "needs_info"
        state["active_agent"] = _AGENT_LABEL["needs_info"]
        state["response_text"] = followup_text
        state["suggestions"] = _build_gap_suggestions(gaps, language, persona, message)
        state["agent_trace"].append(
            make_step(
                agent="Router",
                action=t(language, "Smart follow-up", "متابعة ذكية"),
                tool="requirement_engine",
                reasoning=t(
                    language,
                    f"Detected missing info ({', '.join(gaps)}) for '{intent}' intent. "
                    "Cross-checked persona, memory, and history. "
                    "Asking structured follow-up questions instead of dispatching.",
                    f"تم اكتشاف معلومات ناقصة ({', '.join(gaps)}) للنية '{intent}'. "
                    "تم التحقق من الملف الشخصي والذاكرة وسجل المحادثة. "
                    "يتم طرح أسئلة متابعة مهيكلة بدلاً من التوجيه الفوري.",
                ),
                result=f"gaps={gaps}, structured={'yes' if question_set else 'no'}",
            )
        )
        return state

    # State Machine Phase 10 Transition to PLANNING if ready
    if state_machine.can_transition(current_sm_state, ConversationState.PLANNING):
        if "conversation_state" not in state or not state["conversation_state"]:
            state["conversation_state"] = {}
        state["conversation_state"]["current_state"] = ConversationState.PLANNING.value
        
    state["intent"] = intent
    state["active_agent"] = _AGENT_LABEL[intent]
    state["agent_trace"].append(
        make_step(
            agent="Router",
            action=t(language, "Detect intent", "تحديد نية المستخدم"),
            tool=FAST_MODEL,
            reasoning=t(
                language,
                f"Classified message as '{intent}', delegating to {_AGENT_LABEL[intent]}.",
                f"تم تصنيف الرسالة كـ '{intent}' وتفويض المهمة إلى {_AGENT_LABEL_AR[intent]}.",
            ),
            result=intent,
        )
    )
    return state


def _build_gap_suggestions(
    gaps: List[str],
    language: str,
    persona: Optional[UserPersona],
    message: str,
) -> List[str]:
    """Contextual quick-reply suggestions based on detected gaps."""
    dest = _extract_destination_from_msg(message) or (
        persona.preferred_destination if persona else None
    ) or ""

    if language == "ar":
        suggestions = []
        if "duration" in gaps:
            suggestions.extend([
                f"3 أيام في {dest}" if dest else "3 أيام",
                f"5 أيام في {dest}" if dest else "5 أيام",
                f"أسبوع في {dest}" if dest else "أسبوع كامل",
            ])
        elif "destination" in gaps:
            suggestions.extend(["القاهرة", "الإسكندرية", "الأقصر وأسوان"])
        else:
            suggestions.extend(["اقتصادي", "متوسط", "فاخر"])
        return suggestions[:3]

    suggestions = []
    if "duration" in gaps:
        suggestions.extend([
            f"3 days in {dest}" if dest else "3 days",
            f"5 days in {dest}" if dest else "5 days",
            f"A week in {dest}" if dest else "A full week",
        ])
    elif "destination" in gaps:
        suggestions.extend(["Cairo", "Alexandria", "Luxor & Aswan"])
    else:
        suggestions.extend(["Economy budget", "Mid-range", "Luxury"])
    return suggestions[:3]


__all__ = ["route"]
