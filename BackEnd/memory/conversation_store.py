"""
Conversation store — persist chat history in Firestore or memory.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory fallback: {session_id: [messages]}
_conv_store: dict = {}


async def save_message(session_id: str, user_id: str, role: str, content: str, agent_trace: list = None) -> bool:
    """Append a message to a conversation session."""
    message = {
        "role": role,
        "content": content,
        "agent_trace": agent_trace or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        from memory.firebase_client import get_firestore, is_firebase_available
        if is_firebase_available():
            db = get_firestore()
            db.collection("conversations").document(session_id).collection("messages").add(message)
            return True
    except Exception as e:
        logger.warning(f"Firestore write failed, using memory: {e}")

    # Fallback
    if session_id not in _conv_store:
        _conv_store[session_id] = []
    _conv_store[session_id].append(message)
    return True


async def get_conversation_history(session_id: str, limit: int = 10) -> list[dict]:
    """Retrieve last N messages from a session."""
    try:
        from memory.firebase_client import get_firestore, is_firebase_available
        if is_firebase_available():
            db = get_firestore()
            docs = (db.collection("conversations").document(session_id)
                      .collection("messages")
                      .order_by("timestamp")
                      .limit_to_last(limit)
                      .get())
            return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.warning(f"Firestore read failed, using memory: {e}")

    return _conv_store.get(session_id, [])[-limit:]
