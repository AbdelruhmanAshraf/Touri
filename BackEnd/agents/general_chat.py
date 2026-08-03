"""
Fallback conversational agent for greetings / small talk / off-topic queries.
"""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_FALLBACK_EN = (
    "I'm here to help you plan your Egypt trip! "
    "Ask me about itineraries, local restaurants, budget estimates, or attractions."
)
_FALLBACK_AR = (
    "أنا هنا لمساعدتك في التخطيط لرحلتك في مصر! "
    "اسألني عن الجداول السياحية أو المطاعم المحلية أو تقديرات الميزانية أو المعالم."
)

from agents.llm import FAST_MODEL, ainvoke_with_retry, lang_directive, t, safe_extract_text, clean_response
from agents.state import AgentState, make_step

_SUGGESTIONS_EN = [
    "Plan 3 days in Cairo",
    "Best budget hotels in Hurghada",
    "What events are happening this month?",
    "How to get from Cairo to Luxor?",
    "Top restaurants in Alexandria",
    "Medical tourism options in Egypt",
]

_SUGGESTIONS_AR = [
    "خطة 3 أيام في القاهرة",
    "أفضل فنادق اقتصادية في الغردقة",
    "ما الفعاليات هذا الشهر؟",
    "كيف أصل من القاهرة إلى الأقصر؟",
    "أفضل مطاعم الإسكندرية",
    "خيارات السياحة العلاجية في مصر",
]


async def chitchat(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")
    
    persona_ctx = ""
    if persona:
        name = " ".join(filter(None, [persona.first_name, persona.last_name]))
        if name:
            persona_ctx = f" User's name is {name}." if language == "en" else f" اسم المستخدم هو {name}."

    memory_ctx = state.get("memory_context", "")
    memory_line = f"\n{memory_ctx}" if memory_ctx else ""

    try:
        resp = await ainvoke_with_retry(
            [
                SystemMessage(content=lang_directive(language)),
                HumanMessage(
                    content=(
                        f"Respond conversationally and briefly to the user.{persona_ctx}{memory_line}\n\nUser: {message}"
                        if language == "en"
                        else f"أجب بإيجاز ولطف على المستخدم.{persona_ctx}{memory_line}\n\nالمستخدم: {message}"
                    )
                ),
            ],
            model=FAST_MODEL,
            temperature=0.6,
            streaming=False,
        )
        state["response_text"] = clean_response(safe_extract_text(resp.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[general_chat] LLM call failed, using fallback: %s", exc)
        state["response_text"] = _FALLBACK_AR if language == "ar" else _FALLBACK_EN
    state["suggestions"] = _SUGGESTIONS_AR[:3] if language == "ar" else _SUGGESTIONS_EN[:3]
    state["agent_trace"].append(
        make_step(
            agent="Travel Planner",
            action=t(language, "General reply", "رد عام"),
            tool=FAST_MODEL,
            reasoning=t(
                language,
                "Message did not match a specialised intent; produced a friendly conversational reply.",
                "لم تتطابق الرسالة مع نية متخصصة، فتم إعداد رد ودود عام.",
            ),
            result="text",
        )
    )
    return state


__all__ = ["chitchat"]
