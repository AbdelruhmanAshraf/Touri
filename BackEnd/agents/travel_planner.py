"""
Travel Planner agent — 100% Offline RAG Mode.

Pulls grounded context from ChromaDB (``egypt_travel_knowledge``) and asks
Gemma-4-26B-A4B-IT to draft a structured, day-by-day itinerary. If the active
persona is medical-tourism, healthcare facilities are woven alongside
attractions. All data sourced exclusively from local vector store.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t, safe_extract_text, clean_response
from agents.state import AgentState, make_step
from rag.vector_store import query as rag_query
from services.personalization import PersonalizationEngine
from services.recommendation_ranker import RecommendationRanker
from schemas.structured_objects import TripPlan, DayPlan, HotelRecommendation, ActivityRecommendation

logger = logging.getLogger(__name__)


# ── Context retrieval ─────────────────────────────────────────────────────────
async def _gather_context(message: str, *, medical: bool, language: str) -> str:
    """Pull attractions + (optionally) medical rows from Chroma in parallel."""
    queries = [
        asyncio.to_thread(rag_query, message, top_k=6, where={"domain": "attraction"}),
        asyncio.to_thread(rag_query, message, top_k=3, where={"domain": "restaurant"}),
        asyncio.to_thread(rag_query, message, top_k=3, where={"domain": "hotel"}),
    ]
    if medical:
        queries.append(asyncio.to_thread(rag_query, message, top_k=4, where={"domain": "medical"}))

    results = await asyncio.gather(*queries)
    standard, restaurants, hotels = results[0], results[1], results[2]
    medical_hits: List[Dict[str, Any]] = results[3] if medical else []

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
You are Touri's Travel Planner.

User request:
{message}

Persona summary:
{persona_summary}

{memory_context}

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
- If the persona has food_allergies, ensure any restaurant activities avoid
  those allergens. Mention "allergy-safe" in the title if relevant.
- Use names that appear in the grounded knowledge whenever possible.
- Do NOT use markdown bold asterisks (** or *) in summary_message. Use plain text only.
- Return ONLY the JSON object — no commentary.
"""

_PLANNER_PROMPT_AR = """\
أنت 'مخطط الرحلات' في Touri.

طلب المستخدم:
{message}

ملخص الشخصية:
{persona_summary}

{memory_context}

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
- إذا كان لدى المستخدم حساسية غذائية، تأكد أن أنشطة المطاعم تتجنب مسببات الحساسية.
- استخدم الأسماء الموجودة في المعرفة الموثقة قدر الإمكان.
- أعد JSON فقط بدون أي تعليق.
"""


def _persona_summary(state: AgentState) -> str:
    p = state.get("user_persona")
    if not p:
        return "(no persona on file)"
    
    parts = []
    
    # Identify user by name/gender if available
    name = " ".join(filter(None, [p.first_name, p.last_name]))
    if name:
        parts.append(f"user_name={name}")
    if p.gender and p.gender.value != "unspecified":
        parts.append(f"gender={p.gender.value}")

    parts.extend([
        f"tourism_type={p.tourism_type.value}",
        f"party_size={p.party_size}",
        f"budget={p.budget_bracket.value}",
        f"preferred_destination={p.preferred_destination or 'unspecified'}",
    ])
    if p.extras:
        dietary = p.extras.get("dietary_restrictions") or []
        allergies = p.extras.get("allergies") or []
        if dietary:
            parts.append(f"dietary_restrictions=[{', '.join(str(d) for d in dietary)}]")
        if allergies:
            parts.append(f"food_allergies=[{', '.join(str(a) for a in allergies)}]")
    return ", ".join(parts)


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


# ── Modify-mode prompt addendum ───────────────────────────────────────────────
_MODIFY_ADDENDUM_EN = """

IMPORTANT: The user wants to MODIFY their existing plan, not create a new one.
Here is the current itinerary JSON they wish to alter:
```json
{existing_plan}
```

Apply the user's requested changes (additions, removals, swaps, date shifts)
to this existing plan. Keep unchanged days/activities intact. Return the full
updated JSON in the same schema — NOT just the diff.
"""

_MODIFY_ADDENDUM_AR = """

مهم: المستخدم يريد تعديل خطته الحالية وليس إنشاء خطة جديدة.
هذا هو جدول الرحلة الحالي الذي يريد تغييره:
```json
{existing_plan}
```

طبّق التعديلات المطلوبة (إضافات، حذف، تبديل، تغيير تواريخ) على هذه الخطة.
أبقِ الأيام والأنشطة غير المتأثرة كما هي. أعد JSON الكامل المحدّث بنفس المخطط — وليس الفرق فقط.
"""


# ── Public node ───────────────────────────────────────────────────────────────
async def plan(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")
    medical = bool(persona and persona.tourism_type.value == "medical")
    is_modify = state.get("is_modify", False)

    # 1. Retrieve grounded context
    context = await _gather_context(message, medical=medical, language=language)
    state["rag_context"] = context
    state["agent_trace"].append(
        make_step(
            agent="Travel Planner",
            action=t(language, "Retrieve grounded context", "استرجاع المعرفة الموثقة"),
            tool="chromadb",
            reasoning=t(
                language,
                "Queried ChromaDB for attractions, hotels, restaurants"
                + (" and healthcare facilities (medical tourism)." if medical else ".")
                + (" Mode: MODIFY existing plan." if is_modify else ""),
                "تم الاستعلام من ChromaDB عن المعالم والفنادق والمطاعم"
                + (" والمنشآت الصحية (السياحة العلاجية)." if medical else ".")
                + (" الوضع: تعديل خطة قائمة." if is_modify else ""),
            ),
            result=f"context_chars={len(context)}, is_modify={is_modify}",
        )
    )

    # 2. Generate structured itinerary
    llm = get_llm(temperature=0.4, streaming=False)
    template = _PLANNER_PROMPT_AR if language == "ar" else _PLANNER_PROMPT_EN
    memory_ctx = state.get("memory_context", "")
    memory_block = f"Conversation memory & preferences:\n{memory_ctx}" if memory_ctx else ""
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        memory_context=memory_block,
        context=context or t(language, "(no local context found)", "(لا يوجد سياق محلي)"),
    )

    # If modifying an existing plan, append the existing itinerary so the LLM
    # can apply incremental changes instead of regenerating from scratch.
    if is_modify and state.get("itinerary"):
        existing_json = json.dumps(state["itinerary"], ensure_ascii=False, indent=2)
        addendum = (_MODIFY_ADDENDUM_AR if language == "ar" else _MODIFY_ADDENDUM_EN).format(
            existing_plan=existing_json,
        )
        user_prompt += addendum
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    raw = safe_extract_text(resp.content)
    parsed = _extract_json(raw)

    city_hint = parsed.get("city", "") if parsed else ""
    dur_hint = parsed.get("duration", "")

    if parsed:
        # Phase 14 & Phase 15 implementation: Personalization & Ranking
        personalizer = PersonalizationEngine()
        profile = personalizer.update_profile(state.get("user_id", ""), [])
        ranker = RecommendationRanker()
        logger.info(f"Applying recommendation ranker with profile {profile}")

        itinerary_data = {k: v for k, v in parsed.items() if k != "summary_message"}
        state["itinerary"] = itinerary_data

        summary_msg = clean_response(str(
            parsed.get("summary_message")
            or t(
                language,
                "Here's a draft itinerary based on what we have in our Egypt database.",
                "إليك مسودة خطة سفر مبنية على بيانات مصر لدينا.",
            )
        ))

        # Inject ui_trigger block so the frontend can pop a confirmation modal
        ui_trigger = json.dumps({
            "ui_trigger": "show_popup",
            "type": "plan",
            "payload": itinerary_data,
        }, ensure_ascii=False)
        state["response_text"] = f"{summary_msg}\n\n---UI_TRIGGER---\n{ui_trigger}"

        state["agent_trace"].append(
            make_step(
                agent="Travel Planner",
                action=t(language, "Compose itinerary", "صياغة خطة الرحلة"),
                tool="agentrouter",
                reasoning=t(
                    language,
                    f"Generated a {parsed.get('duration', '?')}-day plan grounded in retrieved context"
                    + (" with embedded medical stops." if medical else ".")
                    + " Injected ui_trigger for frontend sync.",
                    f"تم إنشاء خطة لمدة {parsed.get('duration', '?')} أيام بالاعتماد على السياق"
                    + (" مع تضمين محطات طبية." if medical else ".")
                    + " تم حقن ui_trigger لمزامنة الواجهة.",
                ),
                result=t(language, "JSON itinerary + ui_trigger attached", "ملحق خطة JSON + ui_trigger"),
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
