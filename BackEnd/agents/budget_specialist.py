"""
Budget Specialist agent — 100% Offline RAG Mode.

Combines:
  * ChromaDB lodging facts from ``egypt_travel_knowledge``.
  * ChromaDB transport/attraction pricing data.
  * Fallback pricing heuristic models matched to budget brackets.
  * Gemini to merge them into a structured ``budget_breakdown``.

All external web search (Tavily) is BYPASSED for pure local vector routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t, safe_extract_text, clean_response
from agents.state import AgentState, make_step
from rag.vector_store import query as rag_query
# BYPASSED: Tavily web search disabled for pure offline RAG mode.
# from tools.web_search import search_live_travel_data

logger = logging.getLogger(__name__)


# ── Fallback pricing heuristics (offline mode) ──────────────────────────────
_BUDGET_HEURISTICS = {
    "economy": {
        "flights_per_person": 350,
        "accommodation_per_night": 40,
        "meals_per_day": 20,
        "activities_per_day": 15,
        "transport_per_day": 10,
    },
    "mid_range": {
        "flights_per_person": 550,
        "accommodation_per_night": 90,
        "meals_per_day": 45,
        "activities_per_day": 30,
        "transport_per_day": 20,
    },
    "luxury": {
        "flights_per_person": 900,
        "accommodation_per_night": 200,
        "meals_per_day": 80,
        "activities_per_day": 60,
        "transport_per_day": 40,
    },
}


# ── Prompts ──────────────────────────────────────────────────────────────────
_BUDGET_PROMPT_EN = """\
You are Touri's Budget Specialist (Offline RAG Mode).

Traveller question:
{message}

Persona summary:
{persona_summary}

{memory_context}

Local lodging context (ChromaDB):
---
{lodging}
---

Local transport and attraction pricing (ChromaDB):
---
{transport}
---

Fallback pricing heuristics (use ONLY when no specific data exists in the contexts above):
---
{heuristics}
---

Return a JSON object with this exact shape (no commentary):

{{
  "city": "<primary city>",
  "duration": <int days>,
  "trip_type": "<leisure|medical|cultural|business>",
  "people": <int travellers>,
  "currency": "USD",
  "breakdown": {{
    "flights": <int>,
    "accommodation": <int>,
    "meals": <int>,
    "activities": <int>,
    "local_transport": <int>
  }},
  "total_usd": <int>,
  "per_person_usd": <int>,
  "summary_message": "<friendly 2-3 sentence rundown>"
}}

Rules:
- Every cost is in whole-number USD.
- Prefer prices visible in the ChromaDB contexts above; use heuristic baselines only when no source data exists.
- Reference approximate EGP→USD rate of 1 USD ≈ 50 EGP in summary_message.
- Do NOT use markdown bold asterisks in summary_message. Use plain text only.
- Return JSON only.
"""

_BUDGET_PROMPT_AR = """\
أنت 'خبير الميزانية' في Touri (وضع RAG المحلي).

سؤال المسافر:
{message}

ملخص الشخصية:
{persona_summary}

{memory_context}

سياق الإقامة المحلي (ChromaDB):
---
{lodging}
---

سياق النقل والمعالم السياحية (ChromaDB):
---
{transport}
---

نماذج تسعير احتياطية (استخدمها فقط عند عدم وجود بيانات محددة):
---
{heuristics}
---

أعد JSON بهذا الشكل بالضبط (بدون أي تعليق):

{{
  "city": "<المدينة>",
  "duration": <عدد الأيام>,
  "trip_type": "<leisure|medical|cultural|business>",
  "people": <عدد المسافرين>,
  "currency": "USD",
  "breakdown": {{
    "flights": <عدد>,
    "accommodation": <عدد>,
    "meals": <عدد>,
    "activities": <عدد>,
    "local_transport": <عدد>
  }},
  "total_usd": <عدد>,
  "per_person_usd": <عدد>,
  "summary_message": "<ملخص ودود من جملتين أو ثلاث>"
}}

شروط:
- جميع التكاليف بالدولار الأمريكي وأرقام صحيحة.
- استخدم الأسعار الموجودة في سياق ChromaDB قدر الإمكان، واستخدم النماذج الاحتياطية فقط عند الضرورة.
- اذكر سعر صرف تقريبي 1 دولار ≈ 50 جنيه مصري ضمن summary_message.
- لا تستخدم نجوم markdown في summary_message. استخدم نص عادي فقط.
- أعد JSON فقط.
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
            parts.append(f"allergies=[{', '.join(str(a) for a in allergies)}]")
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


# ── Public node ───────────────────────────────────────────────────────────────
async def calculate(state: AgentState) -> AgentState:
    language = state.get("language", "en")
    message = state.get("user_message", "")

    # 1+2. Parallel ChromaDB queries for lodging and transport/attraction data
    lodging_hits, transport_hits = await asyncio.gather(
        asyncio.to_thread(rag_query, message, top_k=4, where={"domain": "hotel"}),
        asyncio.to_thread(rag_query, message, top_k=4, where={"domain": "attraction"}),
    )
    lodging_text = "\n\n".join(h["text"] for h in lodging_hits)
    transport_text = "\n\n".join(h["text"] for h in transport_hits)
    state["agent_trace"].append(
        make_step(
            agent="Budget Specialist",
            action=t(language, "Fetch pricing data", "جلب بيانات التسعير"),
            tool="chromadb",
            reasoning=t(
                language,
                f"Parallel-queried ChromaDB for lodging ({len(lodging_hits)} hits) and "
                f"attraction/transport ({len(transport_hits)} hits) pricing data.",
                f"تم الاستعلام بالتوازي من ChromaDB عن بيانات الإقامة ({len(lodging_hits)} نتيجة) "
                f"والمعالم/النقل ({len(transport_hits)} نتيجة).",
            ),
            result=f"lodging={len(lodging_hits)}, transport={len(transport_hits)}",
        )
    )

    # 3. Resolve budget bracket for heuristic fallback
    persona = state.get("user_persona")
    bracket = "mid_range"
    if persona and persona.budget_bracket:
        bracket = persona.budget_bracket.value
    heuristics = _BUDGET_HEURISTICS.get(bracket, _BUDGET_HEURISTICS["mid_range"])
    heuristics_text = "\n".join(f"  {k}: ${v}" for k, v in heuristics.items())
    heuristics_text = f"Budget bracket: {bracket}\n{heuristics_text}"

    # 4. Compose breakdown via Gemini (no live web data)
    llm = get_llm(temperature=0.2, streaming=False)
    template = _BUDGET_PROMPT_AR if language == "ar" else _BUDGET_PROMPT_EN
    memory_ctx = state.get("memory_context", "")
    memory_block = f"Conversation memory & preferences:\n{memory_ctx}" if memory_ctx else ""
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        memory_context=memory_block,
        lodging=lodging_text or t(language, "(no local lodging matches)", "(لا توجد فنادق مطابقة)"),
        transport=transport_text or t(language, "(no local transport data)", "(لا توجد بيانات نقل محلية)"),
        heuristics=heuristics_text,
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    raw = safe_extract_text(resp.content)
    parsed = _extract_json(raw)

    if parsed:
        budget_data = {k: v for k, v in parsed.items() if k != "summary_message"}
        state["budget_breakdown"] = budget_data

        summary_msg = clean_response(str(
            parsed.get("summary_message")
            or t(
                language,
                "Here is a fresh budget breakdown.",
                "إليك تفصيل ميزانية محدّث.",
            )
        ))

        # Inject ui_trigger block so the frontend can pop a budget-sync modal
        ui_trigger = json.dumps({
            "ui_trigger": "show_popup",
            "type": "budget",
            "payload": budget_data,
        }, ensure_ascii=False)
        state["response_text"] = f"{summary_msg}\n\n---UI_TRIGGER---\n{ui_trigger}"

        state["agent_trace"].append(
            make_step(
                agent="Budget Specialist",
                action=t(language, "Assemble breakdown", "تجميع تفاصيل الميزانية"),
                tool="agentrouter",
                reasoning=t(
                    language,
                    f"Synthesised total_usd={parsed.get('total_usd')} for "
                    f"{parsed.get('duration', '?')} days, "
                    f"{parsed.get('people', '?')} travellers. "
                    f"Injected ui_trigger for frontend sync.",
                    f"تم تجميع التكلفة الإجمالية {parsed.get('total_usd')} دولار لـ "
                    f"{parsed.get('duration', '?')} أيام و {parsed.get('people', '?')} مسافر. "
                    f"تم حقن ui_trigger لمزامنة الواجهة.",
                ),
                result="json_attached + ui_trigger",
            )
        )
    else:
        state["budget_breakdown"] = None
        state["response_text"] = raw or t(
            language,
            "I couldn't build a confident budget right now. Try sharing destination, days, and party size.",
            "تعذّر بناء ميزانية دقيقة الآن. هل يمكنك ذكر الوجهة وعدد الأيام والمسافرين؟",
        )

    city_hint = (parsed or {}).get("city", "")
    if language == "ar":
        state["suggestions"] = [
            f"هل يمكنك تفصيل أسعار الفنادق{'في ' + city_hint if city_hint else ''}؟",
            "خطط رحلة كاملة ضمن هذه الميزانية",
            "ما خيارات المواصلات المتاحة؟",
        ]
    else:
        state["suggestions"] = [
            f"Can you break down hotel prices{'in ' + city_hint if city_hint else ''}?",
            "Plan a full trip within this budget",
            "What transport options are available?",
        ]
    return state


__all__ = ["calculate"]
