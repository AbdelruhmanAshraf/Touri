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
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langgraph.graph import END, StateGraph

from agents.budget_specialist import calculate as budget_node
from agents.general_chat import chitchat as general_node
from agents.local_concierge import recommend as concierge_node
from agents.router_agent import route as router_node
from agents.state import AgentState, fresh_state
from agents.travel_planner import plan as planner_node


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


# ── Convenience: invoke + stream ──────────────────────────────────────────────
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


__all__ = ["build_graph", "run_chat"]
