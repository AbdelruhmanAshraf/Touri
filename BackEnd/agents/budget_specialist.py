"""
Budget Specialist agent.

Combines:
  * Live Tavily web search for flight prices / FX rates / current costs.
  * ChromaDB lodging facts from ``egypt_travel_knowledge``.
  * Gemini to merge them into a structured ``budget_breakdown``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, lang_directive, t
from agents.state import AgentState, make_step
from rag.vector_store import query as rag_query
from tools.web_search import search_live_travel_data

logger = logging.getLogger(__name__)


# ── Prompts ──────────────────────────────────────────────────────────────────
_BUDGET_PROMPT_EN = """\
You are TripMind's Budget Specialist.

Traveller question:
{message}

Persona summary:
{persona_summary}

Local lodging context (ChromaDB):
---
{lodging}
---

Live web context (Tavily — may include flight prices, exchange rates, currency notes):
---
{live}
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
- Every cost is in **whole-number USD**.
- Prefer prices visible in the contexts above; only estimate when no source data exists.
- If the live web context mentions a current EGP→USD rate, mention it inside summary_message.
- Return JSON only.
"""

_BUDGET_PROMPT_AR = """\
أنت 'خبير الميزانية' في TripMind.

سؤال المسافر:
{message}

ملخص الشخصية:
{persona_summary}

سياق الإقامة المحلي (ChromaDB):
---
{lodging}
---

السياق المباشر من الويب (Tavily — قد يحوي أسعار الطيران وأسعار الصرف):
---
{live}
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
- استخدم الأسعار الموجودة في السياق قدر الإمكان، ولا تخمن إلا عند الضرورة.
- إذا ذكر السياق المباشر سعر صرف حالي للجنيه إلى الدولار، اذكره ضمن summary_message.
- أعد JSON فقط.
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

    # 1. ChromaDB lodging context
    lodging_hits = rag_query(message, top_k=4, where={"domain": "hotel"})
    lodging_text = "\n\n".join(h["text"] for h in lodging_hits)
    state["agent_trace"].append(
        make_step(
            agent="Budget Specialist",
            action=t(language, "Fetch lodging fees", "جلب أسعار الإقامة"),
            tool="chromadb",
            reasoning=t(
                language,
                "Pulled hotel rows from the Egypt knowledge base for accommodation baselines.",
                "تم استرجاع بيانات الفنادق من قاعدة المعرفة لاحتساب الإقامة.",
            ),
            result=f"hits={len(lodging_hits)}",
        )
    )

    # 2. Live Tavily search for flight prices / FX
    try:
        live = await search_live_travel_data(
            f"latest flight prices and USD to EGP exchange rate — {message}",
            max_results=4,
            search_depth="advanced",
        )
        live_context = live.as_llm_context(max_hits=4, max_chars=600)
        state["web_context"] = live_context
        state["agent_trace"].append(
            make_step(
                agent="Budget Specialist",
                action=t(language, "Live web pricing", "بحث مباشر عن الأسعار"),
                tool="tavily",
                reasoning=t(
                    language,
                    "Queried Tavily for live flight prices, FX rates, and recent travel deals.",
                    "تم استعلام Tavily للحصول على أسعار الطيران الحية وأسعار الصرف.",
                ),
                result=f"hits={len(live.hits)}, has_answer={bool(live.answer)}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        live_context = ""
        state["agent_trace"].append(
            make_step(
                agent="Budget Specialist",
                action=t(language, "Live web pricing", "بحث مباشر عن الأسعار"),
                tool="tavily",
                reasoning=t(
                    language,
                    f"Tavily call failed ({exc}); proceeding with local lodging only.",
                    f"فشل استدعاء Tavily ({exc})؛ سيتم الاستمرار بالأسعار المحلية فقط.",
                ),
                result="error",
            )
        )

    # 3. Compose breakdown via Gemini
    llm = get_llm(temperature=0.2, streaming=False)
    template = _BUDGET_PROMPT_AR if language == "ar" else _BUDGET_PROMPT_EN
    user_prompt = template.format(
        message=message,
        persona_summary=_persona_summary(state),
        lodging=lodging_text or t(language, "(no local lodging matches)", "(لا توجد فنادق مطابقة)"),
        live=live_context or t(language, "(no live data)", "(لا توجد بيانات حية)"),
    )
    resp = await llm.ainvoke(
        [SystemMessage(content=lang_directive(language)), HumanMessage(content=user_prompt)]
    )
    raw = (resp.content or "").strip()
    parsed = _extract_json(raw)

    if parsed:
        state["budget_breakdown"] = {k: v for k, v in parsed.items() if k != "summary_message"}
        state["response_text"] = str(
            parsed.get("summary_message")
            or t(
                language,
                "Here is a fresh budget breakdown.",
                "إليك تفصيل ميزانية محدّث.",
            )
        )
        state["agent_trace"].append(
            make_step(
                agent="Budget Specialist",
                action=t(language, "Assemble breakdown", "تجميع تفاصيل الميزانية"),
                tool="agentrouter",
                reasoning=t(
                    language,
                    f"Synthesised total_usd={parsed.get('total_usd')} for "
                    f"{parsed.get('duration', '?')} days, "
                    f"{parsed.get('people', '?')} travellers.",
                    f"تم تجميع التكلفة الإجمالية {parsed.get('total_usd')} دولار لـ "
                    f"{parsed.get('duration', '?')} أيام و {parsed.get('people', '?')} مسافر.",
                ),
                result="json_attached",
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
