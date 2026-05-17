"""
Local Concierge agent.

Pure semantic RAG over the Egypt knowledge base, focused on dining, events
and hidden spots, biased by the active ``UserPersona``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t
from agents.state import AgentState, make_step
from rag.vector_store import query as rag_query

logger = logging.getLogger(__name__)


def _gather(message: str, persona) -> str:
    diet_hint = ""
    if persona and persona.extras:
        dietary = persona.extras.get("dietary_restrictions") or []
        if dietary:
            diet_hint = " " + " ".join(str(d) for d in dietary)

    restaurants = rag_query(message + diet_hint, top_k=4, where={"domain": "restaurant"})
    attractions = rag_query(message, top_k=4, where={"domain": "attraction"})
    events = rag_query(message, top_k=3, where={"domain": "event"})

    sections: List[str] = []
    if restaurants:
        sections.append("## Dining\n" + "\n\n".join(h["text"] for h in restaurants))
    if attractions:
        sections.append("## Attractions & hidden gems\n" + "\n\n".join(h["text"] for h in attractions))
    if events:
        sections.append("## Events\n" + "\n\n".join(h["text"] for h in events))
    return "\n\n".join(sections).strip()


_CONCIERGE_PROMPT_EN = """\
You are TripMind's Local Concierge.

Traveller question:
{message}

Persona summary:
{persona_summary}

Grounded context from the Egypt knowledge base:
---
{context}
---

Write a friendly, well-organised reply with these requirements:
- Recommend 3-5 specific items pulled from the grounded context — use names,
  cities, and any rating/price detail that's available.
- Group your suggestions with brief Markdown subheadings (e.g. "Dining",
  "Hidden gems", "Events").
- Tailor recommendations to the persona (dietary needs, party size, leisure
  vs. medical) when the data supports it.
- Keep the whole reply under 220 words.
"""

_CONCIERGE_PROMPT_AR = """\
أنت 'الكونسيرج المحلي' في TripMind.

سؤال المسافر:
{message}

ملخص الشخصية:
{persona_summary}

السياق الموثق من قاعدة بيانات مصر:
---
{context}
---

اكتب ردًا دافئًا ومنظمًا وفق الشروط:
- اقترح 3-5 خيارات محددة مستقاة من السياق فقط، مع ذكر الاسم والمدينة وأي تفاصيل تقييم أو سعر.
- جمّع المقترحات تحت عناوين قصيرة (مثل "مطاعم"، "أماكن خفية"، "فعاليات").
- خصّص الاقتراحات بحسب ملف المستخدم (الحمية، حجم المجموعة، نوع السياحة).
- الرد لا يتجاوز 220 كلمة.
"""


def _persona_summary(state: AgentState) -> str:
    p = state.get("user_persona")
    if not p:
        return "(no persona on file)"
    return (
        f"tourism_type={p.tourism_type.value}, "
        f"party_size={p.party_size}, "
        f"budget={p.budget_bracket.value}, "
        f"preferred_destination={p.preferred_destination or 'unspecified'}, "
        f"dietary={','.join(str(d) for d in (p.extras.get('dietary_restrictions') or []))}"
    )


async def recommend(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")

    context = _gather(message, persona)
    state["rag_context"] = context
    state["agent_trace"].append(
        make_step(
            agent="Local Concierge",
            action=t(language, "Personalised RAG lookup", "بحث دلالي مخصص"),
            tool="chromadb",
            reasoning=t(
                language,
                "Queried restaurants, attractions and events filtered by the user's persona.",
                "تم البحث عن المطاعم والمعالم والفعاليات حسب ملف المستخدم.",
            ),
            result=f"context_chars={len(context)}",
        )
    )

    llm = get_llm(temperature=0.5, streaming=False)
    template = _CONCIERGE_PROMPT_AR if language == "ar" else _CONCIERGE_PROMPT_EN
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        context=context or t(language, "(no matches in local data)", "(لا توجد نتائج محلية)"),
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    state["response_text"] = (resp.content or "").strip()
    state["agent_trace"].append(
        make_step(
            agent="Local Concierge",
            action=t(language, "Compose recommendations", "صياغة الاقتراحات"),
            tool="agentrouter",
            reasoning=t(
                language,
                "Synthesised concierge recommendations grounded in the retrieved Egypt rows.",
                "تم تكوين اقتراحات الكونسيرج مستندة إلى بيانات مصر المسترجعة.",
            ),
            result=t(language, "text reply", "رد نصي"),
        )
    )
    if language == "ar":
        state["suggestions"] = [
            "خطط رحلة كاملة تشمل هذه الأماكن",
            "ما تكلفة هذه التجربة؟",
            "هل هناك فعاليات قريبة؟",
        ]
    else:
        state["suggestions"] = [
            "Plan a full trip that includes these spots",
            "What's the cost for this experience?",
            "Are there any events nearby?",
        ]
    return state


__all__ = ["recommend"]
