"""
Firestore-backed UserPersona store.

Schema location
---------------
``users/{userId}/persona/profile``

Each user gets a ``persona`` subcollection holding a single ``profile``
document. Storing the persona as a nested document (vs. a flat field on
``users/{userId}``) keeps room for future per-user subcollections such as
``conversations``, ``itineraries``, ``trips``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from memory.firebase_client import get_db

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────────────
class TourismType(str, Enum):
    LEISURE = "leisure"
    MEDICAL = "medical"


class BudgetBracket(str, Enum):
    ECONOMY = "economy"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"


class UserPersona(BaseModel):
    """Structured travel persona persisted in Firestore."""

    user_id: str
    preferred_destination: Optional[str] = Field(
        default=None, description="Country slug, e.g. 'egypt', 'turkey'."
    )
    tourism_type: TourismType = TourismType.LEISURE
    party_size: int = Field(default=1, ge=1, le=20)
    budget_bracket: BudgetBracket = BudgetBracket.MID_RANGE

    # Free-form extensions that don't fit the structured fields above.
    extras: Dict[str, Any] = Field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("preferred_destination", mode="before")
    @classmethod
    def _norm_destination(cls, v):
        if v is None:
            return v
        return str(v).strip().lower().replace(" ", "_") or None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Firestore helpers ─────────────────────────────────────────────────────────
def _persona_doc(user_id: str):
    """``users/{user_id}/persona/profile`` DocumentReference."""
    if not user_id:
        raise ValueError("user_id is required")
    return get_db().collection("users").document(user_id).collection("persona").document("profile")


def _to_firestore(model: UserPersona) -> Dict[str, Any]:
    data = model.model_dump(mode="python")
    # Coerce enums to their string values for Firestore.
    data["tourism_type"] = model.tourism_type.value
    data["budget_bracket"] = model.budget_bracket.value
    return data


def _from_firestore(user_id: str, raw: Dict[str, Any]) -> UserPersona:
    payload = dict(raw or {})
    payload.setdefault("user_id", user_id)
    # Tolerate legacy values.
    if isinstance(payload.get("tourism_type"), str):
        try:
            payload["tourism_type"] = TourismType(payload["tourism_type"].lower())
        except ValueError:
            payload["tourism_type"] = TourismType.LEISURE
    if isinstance(payload.get("budget_bracket"), str):
        try:
            payload["budget_bracket"] = BudgetBracket(payload["budget_bracket"].lower())
        except ValueError:
            payload["budget_bracket"] = BudgetBracket.MID_RANGE
    return UserPersona(**payload)


# ── Public CRUD ───────────────────────────────────────────────────────────────
async def get_persona(user_id: str) -> Optional[UserPersona]:
    """Fetch persona or ``None`` if it doesn't exist yet."""
    snap = _persona_doc(user_id).get()
    if not snap.exists:
        return None
    return _from_firestore(user_id, snap.to_dict() or {})


async def get_or_create_persona(user_id: str) -> UserPersona:
    """Fetch existing persona or create a default one."""
    existing = await get_persona(user_id)
    if existing is not None:
        return existing
    now = _now()
    default = UserPersona(user_id=user_id, created_at=now, updated_at=now)
    _persona_doc(user_id).set(_to_firestore(default))
    logger.info("[persona] created default for user=%s", user_id)
    return default


async def upsert_persona(persona: UserPersona) -> UserPersona:
    """Create or replace the full persona document."""
    now = _now()
    if persona.created_at is None:
        persona.created_at = now
    persona.updated_at = now
    _persona_doc(persona.user_id).set(_to_firestore(persona))
    logger.info("[persona] upserted user=%s", persona.user_id)
    return persona


async def update_persona_fields(user_id: str, updates: Dict[str, Any]) -> UserPersona:
    """Patch specific fields and return the merged persona."""
    current = await get_or_create_persona(user_id)
    merged = current.model_copy(update={k: v for k, v in updates.items() if v is not None})
    merged.updated_at = _now()
    _persona_doc(user_id).set(_to_firestore(merged), merge=True)
    return merged


async def delete_persona(user_id: str) -> bool:
    """Remove the persona document. Returns True if anything was deleted."""
    snap = _persona_doc(user_id).get()
    if not snap.exists:
        return False
    _persona_doc(user_id).delete()
    logger.info("[persona] deleted user=%s", user_id)
    return True


__all__ = [
    "TourismType",
    "BudgetBracket",
    "UserPersona",
    "get_persona",
    "get_or_create_persona",
    "upsert_persona",
    "update_persona_fields",
    "delete_persona",
]
