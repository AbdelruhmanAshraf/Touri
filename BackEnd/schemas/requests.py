"""
Pydantic request models for Tripmind API (Phase 2).

These mirror the inline schemas in ``routes/chat.py`` so they can be
imported independently by tests, CLI tools, or future micro-services.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None
    language: str = Field(default="en", pattern=r"^(en|ar)$")
    history: List[ChatMessage] = Field(default_factory=list)


class PersonaWrite(BaseModel):
    """Payload accepted by POST /api/user/{uid}/persona."""

    preferred_destination: Optional[str] = None
    tourism_type: Optional[str] = Field(default=None, pattern=r"^(leisure|medical)$")
    party_size: Optional[int] = Field(default=None, ge=1, le=20)
    budget_bracket: Optional[str] = Field(
        default=None, pattern=r"^(economy|mid_range|luxury)$"
    )
    extras: Optional[Dict[str, Any]] = None
