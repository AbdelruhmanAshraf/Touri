"""
LangGraph wiring for the Tripmind multi-agent workflow.

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

Streaming: ``stream_chat()`` yields intermediate events (node enter/exit +
agent_trace steps) that the WebSocket handler maps directly to the frontend's
live typing animation and trace panel.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, Literal, Optional

from langgraph.graph import END, StateGraph

from agents.budget_specialist import calculate as budget_node
from agents.general_chat import chitchat as general_node
from agents.local_concierge import recommend as concierge_node
from agents.router_agent import route as router_node
from agents.state import AgentState, fresh_state
from agents.travel_planner import plan as planner_node


# ── Human-readable node labels (for streaming status) ─────────────────────────
_NODE_LABELS = {
    "router": {"en": "Router Agent", "ar": "وكيل التوجيه"},
    "planner": {"en": "Travel Planner", "ar": "وكيل التخطيط"},
    "budget": {"en": "Budget Specialist", "ar": "خبير الميزانية"},
    "concierge": {"en": "Local Concierge", "ar": "الكونسيرج المحلي"},
    "general": {"en": "Travel Planner", "ar": "وكيل التخطيط"},
}

_NODE_STATUS_MSG = {
    "router": {"en": "Analyzing your request...", "ar": "جاري تحليل طلبك..."},
    "planner": {"en": "Building your travel itinerary...", "ar": "جاري بناء جدولك السياحي..."},
    "budget": {"en": "Calculating costs and budget...", "ar": "جاري حساب التكاليف والميزانية..."},
    "concierge": {"en": "Finding personalized recommendations...", "ar": "جاري البحث عن توصيات مخصصة لك..."},
    "general": {"en": "Preparing response...", "ar": "جاري إعداد الرد..."},
}


# ── Conditional edge ──────────────────────────────────────────────────────────
def _branch(state: AgentState) -> Literal["planner", "budget", "concierge", "general"]:
    intent = state.get("intent", "general")
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
    g.add_node("router", router_node)
    g.add_node("planner", planner_node)
    g.add_node("budget", budget_node)
    g.add_node("concierge", concierge_node)
    g.add_node("general", general_node)

    g.set_entry_point("router")
    g.add_conditional_edges(
        "router",
        _branch,
        {
            "planner": "planner",
            "budget": "budget",
            "concierge": "concierge",
            "general": "general",
        },
    )
    for terminal in ("planner", "budget", "concierge", "general"):
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
    graph = build_graph()
    state = fresh_state(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        language=language if language in ("en", "ar") else "en",
        chat_history=chat_history,
    )
    return await graph.ainvoke(state)


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

    async for event in graph.astream(state, stream_mode="updates"):
        for node_name, node_output in event.items():
            label = _NODE_LABELS.get(node_name, {}).get(lang, node_name)
            status_msg = _NODE_STATUS_MSG.get(node_name, {}).get(lang, "")

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


__all__ = ["build_graph", "run_chat", "stream_chat"]
