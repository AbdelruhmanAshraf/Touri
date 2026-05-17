"""
Travel Planner agent.

Pulls grounded context from ChromaDB (``egypt_travel_knowledge``) and asks
Gemini to draft a structured, day-by-day itinerary. If the active persona is
medical-tourism, healthcare facilities are woven alongside attractions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t
from agents.state import AgentState, make_step
from rag.vector_store import query as rag_query

logger = logging.getLogger(__name__)


# ── Context retrieval ─────────────────────────────────────────────────────────
def _gather_context(message: str, *, medical: bool, language: str) -> str:
    """Pull attractions + (optionally) medical rows from Chroma."""
    standard = rag_query(message, top_k=6, where={"domain": "attraction"})
    restaurants = rag_query(message, top_k=3, where={"domain": "restaurant"})
    hotels = rag_query(message, top_k=3, where={"domain": "hotel"})
    medical_hits: List[Dict[str, Any]] = (
        rag_query(message, top_k=4, where={"domain": "medical"}) if medical else []
    )

    sections: List[str] = []
    if standard:
        sections.append("## Attractions\n" + "\n\n".join(h["text"] for h in standard))
    if hotels:
        sections.append("## Hotels\n" + "\n\n".join(h["text"] for h in hotels))
    if restaurants:
        sections.append("## Restaurants\n" + "\n\n".join(h["text"] for h in restaurants))
    if medical_hits:
        sections.append(
            "## Healthcare facilities (medical tourism)\n"
            + "\n\n".join(h["text"] for h in medical_hits)
        )
    return "\n\n".join(sections).strip()


# ── Prompt ────────────────────────────────────────────────────────────────────
_PLANNER_PROMPT_EN = """\
You are TripMind's Travel Planner.

User request:
{message}

Persona summary:
{persona_summary}

Grounded knowledge from our Egypt database (use this; do not invent facts):
---
{context}
---

Build a structured day-by-day itinerary as STRICT JSON with this shape:

{{
  "city": "<primary city>",
  "duration": <int days>,
  "transportation": "<concise summary>",
  "days": [
    {{
      "day": 1,
      "date_label": "Day 1",
      "activities": [
        {{
          "time": "Morning|Afternoon|Evening",
          "emoji": "🏛️",
          "title": "<short>",
          "type": "attraction|restaurant|hotel|transport|medical",
          "rating": null
        }}
      ]
    }}
  ],
  "summary_message": "<2-3 sentence friendly intro mentioning city + highlights>"
}}

Constraints:
- 2-4 activities per day, mixing attraction / restaurant / transport.
- If the persona's tourism_type is medical, insert AT LEAST one healthcare
  facility from the medical section as a 'medical' activity per day, and
  keep the rest of the day calm (no strenuous tours back-to-back).
- Use names that appear in the grounded knowledge whenever possible.
- Return ONLY the JSON object — no commentary.
"""

_PLANNER_PROMPT_AR = """\
أنت 'مخطط الرحلات' في TripMind.

طلب المستخدم:
{message}

ملخص الشخصية:
{persona_summary}

المعرفة الموثقة من قاعدة بيانات مصر (استخدمها فقط، لا تختلق):
---
{context}
---

أنشئ خطة يومية مفصلة كـ JSON صارم بهذا الشكل:

{{
  "city": "<المدينة>",
  "duration": <عدد الأيام>,
  "transportation": "<موجز سريع>",
  "days": [
    {{
      "day": 1,
      "date_label": "اليوم 1",
      "activities": [
        {{
          "time": "صباحًا|ظهرًا|مساءً",
          "emoji": "🏛️",
          "title": "<نشاط>",
          "type": "attraction|restaurant|hotel|transport|medical",
          "rating": null
        }}
      ]
    }}
  ],
  "summary_message": "<مقدمة ودودة من جملتين أو ثلاث>"
}}

شروط:
- 2-4 أنشطة لكل يوم.
- إذا كان نوع السياحة طبيًا، أضف على الأقل منشأة صحية واحدة في كل يوم وحافظ على وتيرة هادئة.
- استخدم الأسماء الموجودة في المعرفة الموثقة قدر الإمكان.
- أعد JSON فقط بدون أي تعليق.
"""


def _persona_summary(state: AgentState) -> str:
    p = state.get("user_persona")
    if not p:
        return "(no persona on file)"
    return (
        f"tourism_type={p.tourism_type.value}, "
        f"party_size={p.party_size}, "
        f"budget={p.budget_bracket.value}, "
        f"preferred_destination={p.preferred_destination or 'unspecified'}"
    )


def _extract_json(raw: str) -> Dict[str, Any] | None:
    # Strip markdown code fences that LLMs often wrap around JSON.
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ── Public node ───────────────────────────────────────────────────────────────
async def plan(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")
    medical = bool(persona and persona.tourism_type.value == "medical")

    # 1. Retrieve grounded context
    context = _gather_context(message, medical=medical, language=language)
    state["rag_context"] = context
    state["agent_trace"].append(
        make_step(
            agent="Travel Planner",
            action=t(language, "Retrieve grounded context", "استرجاع المعرفة الموثقة"),
            tool="chromadb",
            reasoning=t(
                language,
                "Queried ChromaDB for attractions, hotels, restaurants"
                + (" and healthcare facilities (medical tourism)." if medical else "."),
                "تم الاستعلام من ChromaDB عن المعالم والفنادق والمطاعم"
                + (" والمنشآت الصحية (السياحة العلاجية)." if medical else "."),
            ),
            result=f"context_chars={len(context)}",
        )
    )

    # 2. Generate structured itinerary
    llm = get_llm(temperature=0.4, streaming=False)
    template = _PLANNER_PROMPT_AR if language == "ar" else _PLANNER_PROMPT_EN
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        context=context or t(language, "(no local context found)", "(لا يوجد سياق محلي)"),
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    raw = (resp.content or "").strip()
    parsed = _extract_json(raw)

    city_hint = parsed.get("city", "") if parsed else ""
    dur_hint = parsed.get("duration", "")

    if parsed:
        state["itinerary"] = {k: v for k, v in parsed.items() if k != "summary_message"}
        state["response_text"] = str(
            parsed.get("summary_message")
            or t(
                language,
                "Here's a draft itinerary based on what we have in our Egypt database.",
                "إليك مسودة خطة سفر مبنية على بيانات مصر لدينا.",
            )
        )
        state["agent_trace"].append(
            make_step(
                agent="Travel Planner",
                action=t(language, "Compose itinerary", "صياغة خطة الرحلة"),
                tool="agentrouter",
                reasoning=t(
                    language,
                    f"Generated a {parsed.get('duration', '?')}-day plan grounded in retrieved context"
                    + (" with embedded medical stops." if medical else "."),
                    f"تم إنشاء خطة لمدة {parsed.get('duration', '?')} أيام بالاعتماد على السياق"
                    + (" مع تضمين محطات طبية." if medical else "."),
                ),
                result=t(language, "JSON itinerary attached", "ملحق خطة JSON"),
            )
        )
    else:
        state["itinerary"] = None
        state["response_text"] = raw or t(
            language,
            "I couldn't structure a full itinerary just now. Want to narrow the request to a city or number of days?",
            "لم أتمكن من تنظيم خطة كاملة الآن. هل تود تحديد المدينة أو عدد الأيام؟",
        )
        state["agent_trace"].append(
            make_step(
                agent="Travel Planner",
                action=t(language, "Compose itinerary", "صياغة خطة الرحلة"),
                tool="agentrouter",
                reasoning=t(
                    language,
                    "LLM returned non-JSON output; falling back to free-form response.",
                    "أعاد النموذج نصاً غير JSON؛ تم اعتماد رد نصي بديل.",
                ),
                result="fallback_text",
            )
        )

    # Contextual follow-up suggestions
    if language == "ar":
        state["suggestions"] = [
            f"ما الميزانية التقديرية لهذه الرحلة{'إلى ' + city_hint if city_hint else ''}؟",
            "أقترح لي مطاعم محلية في المسار",
            "كيف أصل بين المحطات المختلفة؟",
        ]
    else:
        state["suggestions"] = [
            f"What's the estimated budget{'for ' + city_hint if city_hint else ''}?",
            "Recommend local restaurants along this itinerary",
            "How do I travel between these stops?",
        ]
    return state


__all__ = ["plan"]
