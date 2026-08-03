"""
Conversation State Machine — Firestore-backed workflow state tracking.

Firestore structure
-------------------
users/{uid}/conversation_state/{session_id}  → current workflow state

States
------
onboarding → collecting_requirements → planning → budgeting → concierge → refining → completed

Each state transition is validated. The engine never skips states
(except forward jumps triggered by explicit user actions or agent decisions).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from memory.firebase_client import get_db, is_ready as firebase_ready

logger = logging.getLogger(__name__)

# ── State definitions ────────────────────────────────────────────────────────
ConversationStateName = Literal[
    "onboarding",
    "collecting_requirements",
    "planning",
    "budgeting",
    "concierge",
    "refining",
    "completed",
]

ALL_STATES: List[ConversationStateName] = [
    "onboarding",
    "collecting_requirements",
    "planning",
    "budgeting",
    "concierge",
    "refining",
    "completed",
]

VALID_TRANSITIONS: Dict[ConversationStateName, List[ConversationStateName]] = {
    "onboarding": ["collecting_requirements", "planning"],
    "collecting_requirements": ["planning", "budgeting", "collecting_requirements"],
    "planning": ["budgeting", "concierge", "refining", "completed"],
    "budgeting": ["planning", "concierge", "refining", "completed"],
    "concierge": ["planning", "budgeting", "refining", "completed"],
    "refining": ["planning", "budgeting", "concierge", "completed"],
    "completed": ["collecting_requirements", "planning"],
}

REQUIRED_FIELDS = [
    "destination",
    "duration",
    "budget",
    "party_size",
    "trip_type",
    "transportation",
    "hotel_style",
    "activities",
    "dietary",
    "start_date",
]


# ── Pydantic model ──────────────────────────────────────────────────────────
class RequirementsStatus(BaseModel):
    completed: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    total: int = len(REQUIRED_FIELDS)
    percentage: float = 0.0


class ConversationState(BaseModel):
    session_id: str
    current_state: ConversationStateName = "onboarding"
    previous_state: Optional[ConversationStateName] = None
    completed_requirements: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=lambda: list(REQUIRED_FIELDS))
    active_agent: Optional[str] = None
    last_agent_output: Optional[str] = None
    turn_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def requirements_status(self) -> RequirementsStatus:
        pct = (len(self.completed_requirements) / len(REQUIRED_FIELDS) * 100) if REQUIRED_FIELDS else 0.0
        return RequirementsStatus(
            completed=self.completed_requirements,
            missing=self.missing_requirements,
            total=len(REQUIRED_FIELDS),
            percentage=round(pct, 1),
        )

    def can_transition(self, target: ConversationStateName) -> bool:
        return target in VALID_TRANSITIONS.get(self.current_state, [])

    def transition(self, target: ConversationStateName) -> None:
        if not self.can_transition(target):
            logger.warning(
                "[conversation_state] Invalid transition %s → %s",
                self.current_state, target,
            )
            return
        self.previous_state = self.current_state
        self.current_state = target
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_requirement(self, field: str) -> None:
        if field not in self.completed_requirements:
            self.completed_requirements.append(field)
        if field in self.missing_requirements:
            self.missing_requirements.remove(field)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def increment_turn(self) -> None:
        self.turn_count += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()


# ── Firestore CRUD ──────────────────────────────────────────────────────────
def _state_ref(user_id: str, session_id: str):
    db = get_db()
    return db.collection("users").document(user_id).collection("conversation_state").document(session_id)


async def load_conversation_state(user_id: str, session_id: str) -> ConversationState:
    if not firebase_ready():
        return ConversationState(session_id=session_id)
    try:
        ref = _state_ref(user_id, session_id)
        doc = ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["session_id"] = session_id
            return ConversationState(**data)
    except Exception as exc:
        logger.warning("[conversation_state] load failed: %s", exc)
    return ConversationState(session_id=session_id)


async def save_conversation_state(user_id: str, state: ConversationState) -> None:
    if not firebase_ready():
        return
    try:
        ref = _state_ref(user_id, state.session_id)
        ref.set(state.model_dump(exclude={"session_id"}), merge=True)
    except Exception as exc:
        logger.warning("[conversation_state] save failed: %s", exc)


async def list_user_sessions(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """List all chat sessions for a user with metadata, most recent first."""
    if not firebase_ready():
        return []
    try:
        db = get_db()
        sessions_ref = db.collection("users").document(user_id).collection("chats")
        docs = sessions_ref.order_by("last_active", direction="DESCENDING").limit(limit).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["session_id"] = doc.id
            results.append({
                "session_id": doc.id,
                "destination": data.get("title") or data.get("destination", ""),
                "title": data.get("title", ""),
                "preview": data.get("last_message_preview", ""),
                "last_active": data.get("last_active", ""),
                "message_count": data.get("message_count", 0),
                "created_at": data.get("created_at", ""),
            })
        return results
    except Exception as exc:
        logger.warning("[conversation_state] list_sessions failed: %s", exc)
        return []


async def get_session_messages(
    user_id: str, session_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Load messages for a specific session (for chat history replay)."""
    if not firebase_ready():
        return []
    try:
        db = get_db()
        msgs_ref = (
            db.collection("users")
            .document(user_id)
            .collection("chats")
            .document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .limit(limit)
        )
        results = []
        for doc in msgs_ref.stream():
            data = doc.to_dict()
            results.append({
                "role": data.get("role", "user"),
                "content": data.get("content", ""),
                "agent": data.get("agent"),
                "timestamp": data.get("timestamp", ""),
            })
        return results
    except Exception as exc:
        logger.warning("[conversation_state] get_session_messages failed: %s", exc)
        return []


def determine_next_state(
    current: ConversationState,
    intent: str,
    missing_fields: List[str],
) -> Optional[ConversationStateName]:
    """Determine the appropriate next state based on intent and requirements."""
    cur = current.current_state

    if cur == "onboarding":
        return "collecting_requirements"

    if cur == "collecting_requirements":
        if not missing_fields or len(missing_fields) <= 2:
            if intent == "budget_query":
                return "budgeting"
            return "planning"
        return None

    if cur == "planning":
        if intent == "budget_query":
            return "budgeting"
        if intent == "local_info":
            return "concierge"
        return None

    if cur == "budgeting":
        if intent == "local_info":
            return "concierge"
        if intent == "trip_planning":
            return "refining"
        return None

    if cur in ("concierge", "refining"):
        if intent == "trip_planning":
            return "planning" if cur == "refining" else "refining"
        if intent == "budget_query":
            return "budgeting"
        return None

    return None


__all__ = [
    "ConversationState",
    "ConversationStateName",
    "RequirementsStatus",
    "REQUIRED_FIELDS",
    "determine_next_state",
    "get_session_messages",
    "list_user_sessions",
    "load_conversation_state",
    "save_conversation_state",
]
