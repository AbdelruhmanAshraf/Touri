"""
LangGraph state container for the Tripmind multi-agent workflow.

Every node in the graph reads + extends this dict. ``agent_trace`` is the
audit log the frontend's "Agent Trace Panel" renders.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

# Pydantic v2 requires the ``typing_extensions`` flavour of TypedDict on
# Python < 3.12 in order to generate a JSON schema for it.
from typing_extensions import TypedDict

from memory.user_persona import UserPersona


# ── Trace step ────────────────────────────────────────────────────────────────
Language = Literal["en", "ar"]

Intent = Literal[
    "trip_planning",
    "budget_query",
    "local_info",
    "general",
    "fallback",
]


class AgentStep(TypedDict, total=False):
    """One row of the audit trail rendered in the mobile Agent Trace panel."""

    agent: str          # e.g. "Router", "Travel Planner"
    action: str         # short bilingual-ready label
    tool: Optional[str] # tool invoked (chromadb, tavily, gemini, firestore…)
    reasoning: str      # 1-2 sentence rationale in the active language
    result: Optional[str]
    timestamp: str      # ISO-8601 UTC


def make_step(
    *,
    agent: str,
    action: str,
    reasoning: str,
    tool: Optional[str] = None,
    result: Optional[str] = None,
) -> AgentStep:
    return {
        "agent": agent,
        "action": action,
        "reasoning": reasoning,
        "tool": tool,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ── Graph state ───────────────────────────────────────────────────────────────
class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class AgentState(TypedDict, total=False):
    """Top-level state threaded through every LangGraph node."""

    # --- Inputs the route handler sets up before invoking the graph -----------
    user_id: str
    session_id: str
    user_message: str
    language: Language

    # --- Derived during routing ----------------------------------------------
    user_persona: Optional[UserPersona]
    intent: Intent
    active_agent: str

    # --- Conversation context -------------------------------------------------
    chat_history: List[ChatMessage]

    # --- Outputs that downstream agents fill in ------------------------------
    response_text: str
    itinerary: Optional[Dict[str, Any]]
    budget_breakdown: Optional[Dict[str, Any]]
    rag_context: Optional[str]
    web_context: Optional[str]

    # --- Contextual follow-up suggestions for the chat UI --------------------
    # Each agent populates this with 3 short actionable next-step prompts.
    suggestions: List[str]

    # --- Observability --------------------------------------------------------
    agent_trace: List[AgentStep]


def fresh_state(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    language: Language = "en",
    chat_history: Optional[List[ChatMessage]] = None,
) -> AgentState:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "user_message": user_message,
        "language": language,
        "user_persona": None,
        "intent": "general",
        "active_agent": "Router",
        "chat_history": list(chat_history or []),
        "response_text": "",
        "itinerary": None,
        "budget_breakdown": None,
        "rag_context": None,
        "web_context": None,
        "suggestions": [],
        "agent_trace": [],
    }


__all__ = [
    "AgentState",
    "AgentStep",
    "ChatMessage",
    "Intent",
    "Language",
    "fresh_state",
    "make_step",
]
