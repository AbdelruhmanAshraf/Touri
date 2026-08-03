"""
LangGraph wiring for the Touri multi-agent workflow — Offline RAG Mode.

           ┌───────────────┐
           │     router    │
           └───────┬───────┘
                   │ intent
   ┌───────────────┼────────────────────┬───────────────┐
   ▼               ▼                    ▼               ▼
travel_planner  budget_specialist  local_concierge  general_chat
   └───────────────┴────────────────────┴───────────────┘
                   ▼
                  END

All specialist agents rely 100% on local ChromaDB vector lookups.
Streaming: ``stream_chat()`` yields intermediate events (node enter/exit +
agent_trace steps) that the WebSocket handler maps directly to the frontend's
live typing animation and trace panel.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, Literal, Optional

_logger = logging.getLogger(__name__)

from langgraph.graph import END, StateGraph

from agents.budget_specialist import calculate as budget_node
from agents.general_chat import chitchat as general_node
from agents.local_concierge import recommend as concierge_node
from agents.memory_enforcer import enforce_memory as enforcer_node
from agents.memory_manager import load_memory_into_state as memory_node, persist_exchange
from agents.requirements_node import gather_requirements as requirements_node
from agents.router_agent import route as router_node
from agents.state import AgentState, fresh_state
from agents.travel_planner import plan as planner_node


# ── Passthrough node for follow-up questions (router already set response) ───
async def _needs_info_node(state: AgentState) -> AgentState:
    return state


# ── Human-readable node labels (for streaming status) ─────────────────────────
_NODE_LABELS = {
    "memory": {"en": "Memory Manager", "ar": "مدير الذاكرة"},
    "enforcer": {"en": "Memory Enforcer", "ar": "محقق الذاكرة"},
    "router": {"en": "Router Agent", "ar": "وكيل التوجيه"},
    "requirements": {"en": "Requirements Check", "ar": "فحص المتطلبات"},
    "planner": {"en": "Travel Planner", "ar": "وكيل التخطيط"},
    "budget": {"en": "Budget Specialist", "ar": "خبير الميزانية"},
    "concierge": {"en": "Local Concierge", "ar": "الكونسيرج المحلي"},
    "general": {"en": "Travel Planner", "ar": "وكيل التخطيط"},
    "needs_info": {"en": "Touri Assistant", "ar": "مساعد Touri"},
}

_NODE_STATUS_MSG = {
    "memory": {"en": "Loading your profile...", "ar": "جاري تحميل ملفك الشخصي..."},
    "enforcer": {"en": "Applying memory constraints...", "ar": "جاري تطبيق قيود الذاكرة..."},
    "router": {"en": "Analyzing your request...", "ar": "جاري تحليل طلبك..."},
    "requirements": {"en": "Checking trip details...", "ar": "جاري التحقق من تفاصيل الرحلة..."},
    "planner": {"en": "Building your travel itinerary...", "ar": "جاري بناء جدولك السياحي..."},
    "budget": {"en": "Calculating costs and budget...", "ar": "جاري حساب التكاليف والميزانية..."},
    "concierge": {"en": "Finding personalized recommendations...", "ar": "جاري البحث عن توصيات مخصصة لك..."},
    "general": {"en": "Preparing response...", "ar": "جاري إعداد الرد..."},
    "needs_info": {"en": "Getting ready to help...", "ar": "جاري التحضير لمساعدتك..."},
}


# ── Conditional edge ──────────────────────────────────────────────────────────
def _branch(state: AgentState) -> Literal["planner", "budget", "concierge", "general", "needs_info"]:
    intent = state.get("intent", "general")
    if intent == "needs_info":
        return "needs_info"
    if intent == "trip_planning":
        return "planner"
    if intent == "budget_query":
        return "budget"
    if intent == "local_info":
        return "concierge"
    return "general"


# ── Graph factory ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("memory", memory_node)
    g.add_node("enforcer", enforcer_node)
    g.add_node("router", router_node)
    g.add_node("requirements", requirements_node)
    g.add_node("planner", planner_node)
    g.add_node("budget", budget_node)
    g.add_node("concierge", concierge_node)
    g.add_node("general", general_node)
    g.add_node("needs_info", _needs_info_node)

    # Entry: memory → enforcer → router → requirements → branch
    g.set_entry_point("memory")
    g.add_edge("memory", "enforcer")
    g.add_edge("enforcer", "router")
    # Router resolves intent; requirements node checks slots before dispatching
    g.add_edge("router", "requirements")
    g.add_conditional_edges(
        "requirements",
        _branch,
        {
            "planner": "planner",
            "budget": "budget",
            "concierge": "concierge",
            "general": "general",
            "needs_info": "needs_info",
        },
    )
    for terminal in ("planner", "budget", "concierge", "general", "needs_info"):
        g.add_edge(terminal, END)
    return g.compile()


# ── Convenience: invoke (non-streaming) ───────────────────────────────────────
async def run_chat(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    language: str = "en",
    chat_history=None,
) -> AgentState:
    from services.agent_execution_engine import ExecutionEngine
    
    graph = build_graph()
    state = fresh_state(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        language=language if language in ("en", "ar") else "en",
        chat_history=chat_history,
    )
    
    engine = ExecutionEngine()
    # Use ExecutionEngine's retry/recovery mechanics on the graph invocation itself
    result = await engine.execute_with_recovery(graph.ainvoke, state)

    # Persist the exchange asynchronously
    try:
        await persist_exchange(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=result.get("response_text", ""),
            agent=result.get("active_agent"),
            intent=result.get("intent"),
            itinerary=result.get("itinerary"),
            conversation_state_dict=result.get("conversation_state"),
        )
    except Exception as exc:
        _logger.warning("[run_chat] persist_exchange failed: %s", exc)

    return result


# ── Streaming: yields events as each node runs ────────────────────────────────
async def stream_chat(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    language: str = "en",
    chat_history=None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream the LangGraph execution, yielding events:
      - {"type": "node_start", "node": ..., "label": ..., "status_msg": ...}
      - {"type": "node_end", "node": ..., "state": partial_state}
      - {"type": "final", "state": final_state}

    The WebSocket handler maps these to live UI updates.
    """
    graph = build_graph()
    state = fresh_state(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        language=language if language in ("en", "ar") else "en",
        chat_history=chat_history,
    )

    lang = language if language in ("en", "ar") else "en"
    final_state: Optional[AgentState] = None
    gov_label: Optional[str] = None

    async for event in graph.astream(state, stream_mode="updates"):
        for node_name, node_output in event.items():
            # After router runs, extract the governorate-branded label
            if node_name == "router":
                persona = node_output.get("user_persona")
                if persona and persona.preferred_destination:
                    dest = persona.preferred_destination.lower()
                    gov_map = {
                        "cairo": {"en": "Cairo", "ar": "القاهرة"},
                        "alexandria": {"en": "Alexandria", "ar": "الإسكندرية"},
                        "luxor": {"en": "Luxor", "ar": "الأقصر"},
                        "aswan": {"en": "Aswan", "ar": "أسوان"},
                        "hurghada": {"en": "Red Sea", "ar": "البحر الأحمر"},
                        "red sea": {"en": "Red Sea", "ar": "البحر الأحمر"},
                    }
                    for key, labels in gov_map.items():
                        if key in dest:
                            gov_label = labels.get(lang, key.title())
                            break

            label = _NODE_LABELS.get(node_name, {}).get(lang, node_name)
            status_msg = _NODE_STATUS_MSG.get(node_name, {}).get(lang, "")

            # Prefix status with governorate context for domain-aware feel
            if gov_label and node_name != "router":
                gov_prefix = f"[🧠 {gov_label}] " if lang == "en" else f"[🧠 {gov_label}] "
                status_msg = gov_prefix + status_msg

            yield {
                "type": "node_start",
                "node": node_name,
                "label": label,
                "status_msg": status_msg,
            }

            # Emit any new trace steps that this node appended
            trace_steps = node_output.get("agent_trace") or []
            for step in trace_steps:
                yield {"type": "trace", "step": step}

            yield {
                "type": "node_end",
                "node": node_name,
                "state": node_output,
            }

            final_state = node_output

    # Compose a complete final state from what we have
    if final_state is not None:
        yield {"type": "final", "state": final_state}

    # Persist the exchange asynchronously after streaming completes
    try:
        resp_text = (final_state or {}).get("response_text", "")
        await persist_exchange(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=resp_text,
            agent=(final_state or {}).get("active_agent"),
            intent=(final_state or {}).get("intent"),
            itinerary=(final_state or {}).get("itinerary"),
            conversation_state_dict=(final_state or {}).get("conversation_state"),
        )
    except Exception as exc:
        _logger.warning("[stream_chat] persist_exchange failed: %s", exc)


__all__ = ["build_graph", "run_chat", "stream_chat"]
