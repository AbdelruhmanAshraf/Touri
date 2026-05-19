"""
Local Concierge agent — 100% Offline RAG Mode.

Conducts specific restaurant RAG lookups via ChromaDB. Evaluates results
against the user's ``dietary_preference`` (e.g., Halal food only) AND the
``extras.allergies`` boundaries (filtering or labeling entries that contain
allergens). Also surfaces hidden gems, attractions, and events.

Returns structured spots JSON alongside friendly text for the UI pop-up flow.
All data sourced exclusively from local ChromaDB egypt_travel_knowledge dataset.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t, safe_extract_text, clean_response
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


async def _gather(message: str, persona: Optional[UserPersona]) -> tuple[str, int]:
    """Pull restaurants + attractions + events in parallel, filter by dietary/allergies."""
    diet_hint = ""
    allergies: List[str] = []
    if persona and persona.extras:
        dietary = persona.extras.get("dietary_restrictions") or []
        allergies = persona.extras.get("allergies") or []
        if dietary:
            diet_hint = " " + " ".join(str(d) for d in dietary)

    restaurants_raw, attractions, events = await asyncio.gather(
        asyncio.to_thread(rag_query, message + diet_hint, top_k=8, where={"domain": "restaurant"}),
        asyncio.to_thread(rag_query, message, top_k=4, where={"domain": "attraction"}),
        asyncio.to_thread(rag_query, message, top_k=3, where={"domain": "event"}),
    )

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
You are Touri's Local Concierge.

Traveller question:
{message}

Persona summary:
{persona_summary}

{memory_context}

Grounded context from the Egypt knowledge base (already filtered for allergens):
---
{context}
---

{allergen_note}

You MUST respond in TWO parts separated by the marker `---SPOTS_JSON---`:

PART 1 (before marker): A friendly, well-organised text reply:
- Recommend 3-5 specific items pulled from the grounded context — use names,
  cities, and any rating/price detail available.
- Group suggestions with brief subheadings (Dining, Hidden gems, Events).
- If the user has food allergies, explicitly confirm dining picks are safe.
- HALAL ENFORCEMENT: If the persona's dietary_restrictions include "halal",
  you MUST only recommend restaurants that serve halal food. If a restaurant's
  halal status is uncertain from the context, explicitly state that the
  traveller should verify on arrival. NEVER suggest pork-based dishes or
  venues known for non-halal cuisine.
- Keep under 200 words. Do NOT use markdown bold (**) or italic (*) — just plain text.

PART 2 (after marker): A strict JSON array of recommended spots:
```json
[
  {{"name": "...", "city": "...", "type": "restaurant|attraction|event", "rating": 4.5, "price_hint": "$$", "safe_for_allergies": true}}
]
```

Example output format:
Here are my top picks for you...
(text)

---SPOTS_JSON---
[{{"name": "Koshary Abou Tarek", "city": "Cairo", "type": "restaurant", "rating": 4.6, "price_hint": "$", "safe_for_allergies": true}}]
"""

_CONCIERGE_PROMPT_AR = """\
أنت 'الكونسيرج المحلي' في Touri.

سؤال المسافر:
{message}

ملخص الشخصية:
{persona_summary}

{memory_context}

السياق الموثق من قاعدة بيانات مصر (تمت تصفيته من مسببات الحساسية):
---
{context}
---

{allergen_note}

يجب أن يكون ردك من جزأين يفصلهما العلامة `---SPOTS_JSON---`:

الجزء الأول (قبل العلامة): رد نصي دافئ ومنظم:
- اقترح 3-5 خيارات مستقاة من السياق فقط مع الاسم والمدينة والتقييم/السعر.
- جمّع المقترحات تحت عناوين قصيرة (مطاعم، أماكن خفية، فعاليات).
- إذا كان لدى المستخدم حساسية غذائية، أكّد صراحةً أن اختياراتك آمنة.
- تطبيق الحلال: إذا كانت القيود الغذائية تشمل "حلال"، يجب أن تقترح
  فقط المطاعم التي تقدم طعامًا حلالًا. إذا كان وضع الحلال غير مؤكد من
  السياق، اذكر صراحة أنه يجب على المسافر التحقق عند الوصول. لا تقترح
  أبدًا أطباقًا تحتوي على لحم الخنزير أو أماكن معروفة بتقديم طعام غير حلال.
- لا تتجاوز 200 كلمة. لا تستخدم نجوم (**) — نص عادي فقط.

الجزء الثاني (بعد العلامة): مصفوفة JSON صارمة:
```json
[
  {{"name": "...", "city": "...", "type": "restaurant|attraction|event", "rating": 4.5, "price_hint": "$$", "safe_for_allergies": true}}
]
```
"""


def _persona_summary(state: AgentState) -> str:
    p = state.get("user_persona")
    if not p:
        return "(no persona on file)"
    
    parts = []
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
            parts.append(f"dietary=[{', '.join(str(d) for d in dietary)}]")
        if allergies:
            parts.append(f"food_allergies=[{', '.join(str(a) for a in allergies)}]")
    return ", ".join(parts)


async def recommend(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")
    persona = state.get("user_persona")

    context, filtered_count = await _gather(message, persona)
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
    memory_ctx = state.get("memory_context", "")
    memory_block = f"Conversation memory & preferences:\n{memory_ctx}" if memory_ctx else ""
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        memory_context=memory_block,
        context=context or t(language, "(no matches in local data)", "(لا توجد نتائج محلية)"),
        allergen_note=allergen_note,
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    raw_output = safe_extract_text(resp.content)

    # Parse the structured SPOTS_JSON block out of the response
    text_part = raw_output
    spots_json: Optional[List[Dict[str, Any]]] = None
    if "---SPOTS_JSON---" in raw_output:
        parts = raw_output.split("---SPOTS_JSON---", 1)
        text_part = clean_response(parts[0].strip())
        json_part = parts[1].strip()
        # Extract JSON array from possible code fences
        json_cleaned = re.sub(r"```(?:json)?\s*", "", json_part).strip().rstrip("`")
        try:
            spots_json = json.loads(json_cleaned)
        except json.JSONDecodeError:
            # Try to find array pattern
            match = re.search(r"\[.*\]", json_cleaned, re.DOTALL)
            if match:
                try:
                    spots_json = json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

    else:
        text_part = clean_response(text_part)

    state["spots_json"] = spots_json

    # Inject ui_trigger so the frontend pops a "Save spots?" confirmation modal
    if spots_json:
        ui_trigger = json.dumps({
            "ui_trigger": "show_popup",
            "type": "spots",
            "payload": spots_json,
        }, ensure_ascii=False)
        state["response_text"] = f"{text_part}\n\n---UI_TRIGGER---\n{ui_trigger}"
    else:
        state["response_text"] = text_part

    state["agent_trace"].append(
        make_step(
            agent="Local Concierge",
            action=t(language, "Compose recommendations", "صياغة الاقتراحات"),
            tool="gemma-4-26b-a4b-it",
            reasoning=t(
                language,
                f"Synthesised concierge recommendations. Parsed {len(spots_json or [])} structured spots."
                + (" Injected ui_trigger for frontend sync." if spots_json else ""),
                f"تم تكوين اقتراحات الكونسيرج. تم استخراج {len(spots_json or [])} موقع مهيكل."
                + (" تم حقن ui_trigger لمزامنة الواجهة." if spots_json else ""),
            ),
            result=f"spots={len(spots_json or [])}, text_chars={len(text_part)}",
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
