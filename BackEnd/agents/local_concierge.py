"""
Local Concierge agent.

Conducts specific restaurant RAG lookups via ChromaDB. Evaluates results
against the user's ``dietary_preference`` (e.g., Halal food only) AND the
``extras.allergies`` boundaries (filtering or labeling entries that contain
allergens). Also surfaces hidden gems, attractions, and events.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t
from agents.state import AgentState, make_step
from memory.user_persona import UserPersona
from rag.vector_store import query as rag_query

logger = logging.getLogger(__name__)


# ── Allergen keywords for post-retrieval filtering ────────────────────────────
_ALLERGEN_KEYWORDS = {
    "nuts": ["nuts", "peanut", "almond", "walnut", "cashew", "pistachio", "مكسرات", "فول سوداني", "لوز"],
    "dairy": ["dairy", "milk", "cheese", "cream", "butter", "yogurt", "ألبان", "حليب", "جبن"],
    "gluten": ["gluten", "wheat", "bread", "pasta", "flour", "جلوتين", "قمح", "خبز"],
    "seafood": ["seafood", "fish", "shrimp", "crab", "lobster", "مأكولات بحرية", "سمك", "جمبري"],
}


def _contains_allergen(text: str, allergies: List[str]) -> bool:
    """Check if a RAG result text mentions any of the user's allergens."""
    text_lower = text.lower()
    for allergy in allergies:
        allergy_key = allergy.lower().strip()
        keywords = _ALLERGEN_KEYWORDS.get(allergy_key, [allergy_key])
        for kw in keywords:
            if kw.lower() in text_lower:
                return True
    return False


def _gather(message: str, persona: Optional[UserPersona]) -> tuple[str, int]:
    """Pull restaurants + attractions + events, filter by dietary/allergies."""
    diet_hint = ""
    allergies: List[str] = []
    if persona and persona.extras:
        dietary = persona.extras.get("dietary_restrictions") or []
        allergies = persona.extras.get("allergies") or []
        if dietary:
            diet_hint = " " + " ".join(str(d) for d in dietary)

    # Query more results so we have room to filter
    restaurants_raw = rag_query(message + diet_hint, top_k=8, where={"domain": "restaurant"})
    attractions = rag_query(message, top_k=4, where={"domain": "attraction"})
    events = rag_query(message, top_k=3, where={"domain": "event"})

    # Filter restaurants against allergens
    filtered_count = 0
    restaurants: List[Dict[str, Any]] = []
    for hit in restaurants_raw:
        if allergies and _contains_allergen(hit.get("text", ""), allergies):
            filtered_count += 1
            continue
        restaurants.append(hit)
        if len(restaurants) >= 5:
            break

    sections: List[str] = []
    if restaurants:
        sections.append("## Dining (allergen-filtered)\n" + "\n\n".join(h["text"] for h in restaurants))
    if attractions:
        sections.append("## Attractions & hidden gems\n" + "\n\n".join(h["text"] for h in attractions))
    if events:
        sections.append("## Events\n" + "\n\n".join(h["text"] for h in events))
    return "\n\n".join(sections).strip(), filtered_count


_CONCIERGE_PROMPT_EN = """\
You are TripMind's Local Concierge.

Traveller question:
{message}

Persona summary:
{persona_summary}

Grounded context from the Egypt knowledge base (already filtered for allergens):
---
{context}
---

{allergen_note}

Write a friendly, well-organised reply with these requirements:
- Recommend 3-5 specific items pulled from the grounded context — use names,
  cities, and any rating/price detail that's available.
- Group your suggestions with brief Markdown subheadings (e.g. "Dining",
  "Hidden gems", "Events").
- Tailor recommendations to the persona (dietary needs, allergies, party size,
  leisure vs. medical) when the data supports it.
- If the user has food allergies, explicitly confirm that your dining picks
  are safe for them (or note any caveats).
- Keep the whole reply under 250 words.
"""

_CONCIERGE_PROMPT_AR = """\
أنت 'الكونسيرج المحلي' في TripMind.

سؤال المسافر:
{message}

ملخص الشخصية:
{persona_summary}

السياق الموثق من قاعدة بيانات مصر (تمت تصفيته من مسببات الحساسية):
---
{context}
---

{allergen_note}

اكتب ردًا دافئًا ومنظمًا وفق الشروط:
- اقترح 3-5 خيارات محددة مستقاة من السياق فقط، مع ذكر الاسم والمدينة وأي تفاصيل تقييم أو سعر.
- جمّع المقترحات تحت عناوين قصيرة (مثل "مطاعم"، "أماكن خفية"، "فعاليات").
- خصّص الاقتراحات بحسب ملف المستخدم (الحمية، الحساسية الغذائية، حجم المجموعة، نوع السياحة).
- إذا كان لدى المستخدم حساسية غذائية، أكّد صراحةً أن اختياراتك آمنة له.
- الرد لا يتجاوز 250 كلمة.
"""


def _persona_summary(state: AgentState) -> str:
    p = state.get("user_persona")
    if not p:
        return "(no persona on file)"
    parts = [
        f"tourism_type={p.tourism_type.value}",
        f"party_size={p.party_size}",
        f"budget={p.budget_bracket.value}",
        f"preferred_destination={p.preferred_destination or 'unspecified'}",
    ]
    if p.extras:
        dietary = p.extras.get("dietary_restrictions") or []
        allergies = p.extras.get("allergies") or []
        if dietary:
            parts.append(f"dietary=[{', '.join(str(d) for d in dietary)}]")
        if allergies:
            parts.append(f"food_allergies=[{', '.join(str(a) for a in allergies)}]")
    return ", ".join(parts)


async def recommend(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")

    context, filtered_count = _gather(message, persona)
    state["rag_context"] = context

    # Build allergen note for the prompt
    allergies = []
    if persona and persona.extras:
        allergies = persona.extras.get("allergies") or []

    allergen_note = ""
    if allergies:
        allergy_list = ", ".join(str(a) for a in allergies)
        if language == "ar":
            allergen_note = (
                f"⚠️ تنبيه: المستخدم لديه حساسية من: {allergy_list}. "
                f"تم استبعاد {filtered_count} نتيجة تحتوي على مسببات الحساسية. "
                "تأكد أن جميع اقتراحات الطعام آمنة تمامًا."
            )
        else:
            allergen_note = (
                f"⚠️ ALLERGY ALERT: User is allergic to: {allergy_list}. "
                f"{filtered_count} results were filtered out for containing allergens. "
                "Ensure ALL dining suggestions are completely safe."
            )

    state["agent_trace"].append(
        make_step(
            agent="Local Concierge",
            action=t(language, "Personalised RAG lookup", "بحث دلالي مخصص"),
            tool="chromadb",
            reasoning=t(
                language,
                f"Queried restaurants, attractions and events. Filtered {filtered_count} "
                f"results containing allergens ({', '.join(allergies) if allergies else 'none'}).",
                f"تم البحث عن المطاعم والمعالم والفعاليات. تم استبعاد {filtered_count} "
                f"نتيجة تحتوي مسببات حساسية ({', '.join(allergies) if allergies else 'لا يوجد'}).",
            ),
            result=f"context_chars={len(context)}, filtered={filtered_count}",
        )
    )

    llm = get_llm(temperature=0.5, streaming=False)
    template = _CONCIERGE_PROMPT_AR if language == "ar" else _CONCIERGE_PROMPT_EN
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        context=context or t(language, "(no matches in local data)", "(لا توجد نتائج محلية)"),
        allergen_note=allergen_note,
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    state["response_text"] = (resp.content or "").strip()
    state["agent_trace"].append(
        make_step(
            agent="Local Concierge",
            action=t(language, "Compose recommendations", "صياغة الاقتراحات"),
            tool=t(language, "gemma-4-27b-it", "gemma-4-27b-it"),
            reasoning=t(
                language,
                "Synthesised concierge recommendations grounded in allergen-filtered Egypt data.",
                "تم تكوين اقتراحات الكونسيرج مستندة إلى بيانات مصر المفلترة من مسببات الحساسية.",
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
