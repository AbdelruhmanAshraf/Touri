"""
Router agent: persona load + bilingual intent detection + delegation.

Output: ``state['intent']``, ``state['active_agent']``, ``state['user_persona']``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import FAST_MODEL, get_llm, lang_directive, t
from agents.state import AgentState, Intent, make_step
from memory.firebase_client import is_ready as firebase_ready
from memory.user_persona import UserPersona, get_or_create_persona

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
graph. Return JSON only: {"intent": "<one of: trip_planning | budget_query | local_info | general>"}.

Definitions:
- trip_planning: user wants an itinerary, day-by-day plan, route, multi-stop tour.
- budget_query: user asks about cost, price, savings, exchange rate, total spend.
- local_info: user asks for restaurants, dining, cafes, events, hidden gems, attractions.
- general: small talk, greetings, anything not above.

Message:
{message}
"""

_INTENT_PROMPT_AR = """\
صنّف رسالة المسافر إلى نية واحدة فقط من النوايا التالية. أعد JSON فقط:
{"intent": "<trip_planning | budget_query | local_info | general>"}

التعريفات:
- trip_planning: المستخدم يريد خطة رحلة أو جدول يومي.
- budget_query: سؤال عن السعر، التكلفة، الميزانية، سعر الصرف.
- local_info: سؤال عن المطاعم، الفعاليات، الأماكن المحلية أو الخفية.
- general: محادثة عامة أو لا تنطبق الفئات السابقة.

الرسالة:
{message}
"""


async def _llm_intent(message: str, language: str) -> Intent:
    llm = get_llm(model=FAST_MODEL, temperature=0.0, streaming=False)
    prompt = (_INTENT_PROMPT_AR if language == "ar" else _INTENT_PROMPT_EN).format(
        message=message,
    )
    try:
        resp = await llm.ainvoke(
            [SystemMessage(content=lang_directive(language)), HumanMessage(content=prompt)]
        )
        raw = (resp.content or "").strip()
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


# ── Public node ───────────────────────────────────────────────────────────────
_AGENT_LABEL = {
    "trip_planning": "Travel Planner",
    "budget_query": "Budget Specialist",
    "local_info": "Local Concierge",
    "general": "Travel Planner",
    "fallback": "Travel Planner",
}


async def route(state: AgentState) -> AgentState:
    """LangGraph node: enriches state with persona + intent + active_agent."""
    language = state.get("language", "en")
    message = state.get("user_message", "")
    user_id = state.get("user_id", "")

    # 1. Persona
    persona = await _load_persona(user_id)
    state["user_persona"] = persona
    state["agent_trace"].append(
        make_step(
            agent="Router",
            action=t(language, "Load user persona", "تحميل بيانات المستخدم"),
            tool="firestore",
            reasoning=t(
                language,
                "Pulled persona to bias intent (tourism_type, budget bracket, party size).",
                "تم تحميل ملف المستخدم لتحسين فهم النية (نوع السياحة، الميزانية، عدد المسافرين).",
            ),
            result=(
                f"tourism_type={persona.tourism_type.value}, "
                f"party_size={persona.party_size}, "
                f"budget={persona.budget_bracket.value}"
            )
            if persona
            else (None),
        )
    )

    # 2. Intent — try heuristics first, fall back to Gemini
    intent: Intent = _heuristic_intent(message) or await _llm_intent(message, language)

    # 3. Persona override: if user is on Medical tourism and intent is generic,
    #    prefer trip planning so the planner can weave in healthcare facilities.
    if persona and persona.tourism_type.value == "medical" and intent == "general":
        intent = "trip_planning"

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
                f"تم تصنيف الرسالة كـ '{intent}' وتفويض المهمة إلى {_AGENT_LABEL[intent]}.",
            ),
            result=intent,
        )
    )
    return state


__all__ = ["route"]
