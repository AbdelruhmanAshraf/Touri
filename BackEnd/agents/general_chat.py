"""
Fallback conversational agent for greetings / small talk / off-topic queries.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import FAST_MODEL, get_llm, lang_directive, t
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
    llm = get_llm(model=FAST_MODEL, temperature=0.6, streaming=False)

    resp = await llm.ainvoke(
        [
            SystemMessage(content=lang_directive(language)),
            HumanMessage(
                content=(
                    "Respond conversationally and briefly to: " + message
                    if language == "en"
                    else "أجب بإيجاز ولطف على: " + message
                )
            ),
        ]
    )
    state["response_text"] = (resp.content or "").strip()
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
