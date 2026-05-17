"""
Pydantic response models for Tripmind API (Phase 2).

These mirror the inline schemas in ``routes/chat.py`` so they can be
imported independently by tests, CLI tools, or future micro-services.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AgentStep(BaseModel):
    agent: str
    action: str
    tool: Optional[str] = None
    reasoning: Optional[str] = None
    result: Optional[str] = None
    timestamp: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    agent: str
    intent: str
    language: str
    agent_trace: List[AgentStep] = []
    itinerary: Optional[Dict[str, Any]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None


class UserPersonaResponse(BaseModel):
    user_id: str
    preferred_destination: Optional[str] = None
    tourism_type: str = "leisure"
    party_size: int = 1
    budget_bracket: str = "mid_range"
    extras: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    missing_env: List[str] = []
    subsystems: Optional[Dict[str, Any]] = None
