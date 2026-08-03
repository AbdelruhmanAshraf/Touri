"""
Phase 2 chat routes.

Surfaces:
    POST /api/chat                              — single-shot REST chat
    GET  /api/user/{uid}/persona                — read persona from Firestore
    POST /api/user/{uid}/persona                — overwrite / patch persona
    WS   /api/chat/ws                           — streaming chat with live agent_trace
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request, WebSocket, WebSocketDisconnect
from routes.auth import decode_access_token, get_current_user
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from middleware.rate_limit import AI_CHAT_LIMIT, ONBOARDING_LIMIT, check_rate_limit_or_raise
from middleware.output_sanitizer import sanitize_output, sanitize_agent_trace
from middleware.ui_trigger_validator import strip_user_triggers, extract_and_validate_triggers

from agents.mistral_chat import run_multimodal_chat, stream_mistral_chat
from agents.graph import run_chat, stream_chat
from agents.llm import FAST_MODEL, get_llm, lang_directive, clean_response
from agents.state import AgentStep, ChatMessage, fresh_state
from memory.firebase_client import get_db, is_ready as firebase_ready
from memory.user_persona import (
    BudgetBracket,
    TourismType,
    UserPersona,
    delete_persona,
    get_or_create_persona,
    update_persona_fields,
    upsert_persona,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ── Request / response schemas ────────────────────────────────────────────────
class MultimodalPart(BaseModel):
    """One attachment chunk: image, audio, video, or PDF as base64."""

    mime_type: str = Field(..., min_length=3)
    data: str = Field(
        ...,
        max_length=20_000_000,
        description="Base64-encoded blob (no data: prefix).",
    )


class ChatRequest(BaseModel):
    user_id: str
    message: str = Field(..., max_length=10000)
    session_id: Optional[str] = None
    language: str = Field(default="en", pattern=r"^(en|ar)$")
    history: List[ChatMessage] = Field(default_factory=list)
    # Optional multimodal attachments. When present, the request is routed to
    # the native Gemini multimodal handler instead of the LangGraph workflow.
    parts: List[MultimodalPart] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    agent: str
    intent: str
    language: str
    agent_trace: List[AgentStep]
    itinerary: Optional[Dict[str, Any]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None
    spots_json: Optional[List[Dict[str, Any]]] = None
    suggestions: List[str] = []
    structured_questions: Optional[Dict[str, Any]] = None
    conversation_state: Optional[Dict[str, Any]] = None
    requirements_status: Optional[Dict[str, Any]] = None


class PersonaWrite(BaseModel):
    """Payload accepted by POST /api/user/{uid}/persona."""

    preferred_destination: Optional[str] = Field(default=None, max_length=200)
    tourism_type: Optional[str] = Field(
        default=None, pattern=r"^(leisure|medical)$"
    )
    party_size: Optional[int] = Field(default=None, ge=1, le=20)
    budget_bracket: Optional[str] = Field(
        default=None, pattern=r"^(economy|mid_range|luxury)$"
    )
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    gender: Optional[str] = Field(
        default=None, pattern=r"^(male|female|unspecified)$"
    )
    photo_url: Optional[str] = Field(
        default=None, max_length=2048, pattern=r"^https://.*$"
    )
    extras: Optional[Dict[str, Any]] = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _require_firebase() -> None:
    if not firebase_ready():
        raise HTTPException(
            status_code=503,
            detail="Firebase Admin SDK is not configured on the server.",
        )


async def _auto_generate_trip(uid: str, persona: "UserPersona") -> None:
    """
    Background task: fires a synthetic trip-planning chat right after
    onboarding persona is saved, so the Itinerary tab has content immediately.

    The full agent output (message, itinerary, budget breakdown, suggestions)
    is persisted to ``users/{uid}/trips/initial`` in Firestore. The frontend
    Itinerary tab fetches this on mount so the user lands on a populated page.

    Runs silently — errors are logged but never surfaced to the caller.
    """
    try:
        dest = persona.preferred_destination or "Egypt"
        party = persona.party_size or 2
        budget_label = {
            "economy": "budget-friendly",
            "mid_range": "mid-range",
            "luxury": "luxury",
        }.get(persona.budget_bracket.value if persona.budget_bracket else "", "mid-range")
        tourism = persona.tourism_type.value if persona.tourism_type else "leisure"
        prompt = (
            f"Plan a 5-day {tourism} trip to {dest} for {party} people "
            f"with a {budget_label} budget. Include daily activities, "
            f"accommodation suggestions, and an estimated cost breakdown."
        )
        sid = f"auto_{uid[:8]}_{uuid.uuid4().hex[:6]}"
        state = await run_chat(
            user_id=uid,
            session_id=sid,
            user_message=prompt,
            language="en",
            chat_history=[],
        )

        # ── Persist to Firestore so the Itinerary tab can fetch it on mount.
        trip_doc = {
            "session_id": sid,
            "destination": dest,
            "party_size": party,
            "tourism_type": tourism,
            "budget_bracket": budget_label,
            "message": state.get("response_text", ""),
            "itinerary": state.get("itinerary"),
            "budget_breakdown": state.get("budget_breakdown"),
            "suggestions": state.get("suggestions", []),
            "agent": state.get("active_agent"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "auto_onboarding",
        }
        try:
            db = get_db()
            db.collection("users").document(uid).collection("trips").document("initial").set(trip_doc)
            logger.info("[auto_trip] persisted users/%s/trips/initial (dest=%s)", uid, dest)
        except Exception as fs_exc:  # noqa: BLE001
            logger.warning("[auto_trip] firestore persist failed for uid=%s: %s", uid, fs_exc)

    except Exception as exc:  # noqa: BLE001
        logger.warning("[auto_trip] background generation failed for uid=%s: %s", uid, exc)


def _persona_to_dict(p: UserPersona) -> Dict[str, Any]:
    return {
        "user_id": p.user_id,
        "preferred_destination": p.preferred_destination,
        "tourism_type": p.tourism_type.value if p.tourism_type else "leisure",
        "party_size": p.party_size or 1,
        "budget_bracket": p.budget_bracket.value if p.budget_bracket else "mid_range",
        "first_name": p.first_name or "",
        "last_name": p.last_name or "",
        "gender": p.gender.value if p.gender else "unspecified",
        "photo_url": p.photo_url,
        "extras": p.extras or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── REST: chat ────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    current_user_id: str = Depends(get_current_user),
) -> ChatResponse:
    check_rate_limit_or_raise(request, AI_CHAT_LIMIT, user_id=current_user_id)

    # SECURITY: Strip any UI_TRIGGER injection from user messages
    req.message = strip_user_triggers(req.message)

    if req.user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot initiate a chat for another user.",
        )

    if len(req.message) > 10000:
        raise HTTPException(
            status_code=400,
            detail="Message exceeds maximum allowed length of 10,000 characters.",
        )

    total_attachment_bytes = sum(len(p.data) for p in req.parts)
    if total_attachment_bytes > 20_000_000:
        raise HTTPException(
            status_code=400,
            detail="Attachments exceed maximum allowed size limit of 15MB.",
        )

    session_id = req.session_id or str(uuid.uuid4())

    # Branch 1: multimodal — hand off to the native Gemini handler.
    if req.parts:
        try:
            state = await run_multimodal_chat(
                user_id=req.user_id,
                session_id=session_id,
                text=req.message,
                parts=[p.model_dump() for p in req.parts],
                language=req.language,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[chat] multimodal failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to process your request. Please try again.")
    else:
        # Branch 2: standard LangGraph multi-agent workflow.
        try:
            state = await run_chat(
                user_id=req.user_id,
                session_id=session_id,
                user_message=req.message,
                language=req.language,
                chat_history=req.history,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[chat] graph failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to process your request. Please try again.")

    # SECURITY: Sanitize AI output before delivery
    raw_response = clean_response(state.get("response_text", ""))
    safe_response = sanitize_output(raw_response)
    safe_trace = sanitize_agent_trace(state.get("agent_trace", []))

    return ChatResponse(
        session_id=session_id,
        message=safe_response,
        agent=state.get("active_agent", "Travel Planner"),
        intent=state.get("intent", "general"),
        language=state.get("language", req.language),
        agent_trace=safe_trace,
        itinerary=state.get("itinerary"),
        budget_breakdown=state.get("budget_breakdown"),
        spots_json=state.get("spots_json"),
        suggestions=state.get("suggestions", []),
        structured_questions=state.get("structured_questions"),
        conversation_state=state.get("conversation_state"),
        requirements_status=state.get("requirements_status"),
    )


# ── REST: persona CRUD ───────────────────────────────────────────────────────
@router.get("/user/{uid}/persona")
async def get_persona_route(
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot access another user's persona.",
        )
    try:
        persona = await get_or_create_persona(uid)
        return _persona_to_dict(persona)
    except Exception as exc:  # noqa: BLE001
        logger.error("[persona] GET failed for uid=%s: %s", uid, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load persona.")


@router.post("/user/{uid}/persona")
async def upsert_persona_route(
    payload: PersonaWrite,
    background_tasks: BackgroundTasks,
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot modify another user's persona.",
        )
    updates: Dict[str, Any] = {}
    if payload.preferred_destination is not None:
        updates["preferred_destination"] = payload.preferred_destination
    if payload.tourism_type is not None:
        updates["tourism_type"] = TourismType(payload.tourism_type)
    if payload.party_size is not None:
        updates["party_size"] = payload.party_size
    if payload.budget_bracket is not None:
        updates["budget_bracket"] = BudgetBracket(payload.budget_bracket)
    if payload.first_name is not None:
        updates["first_name"] = payload.first_name
    if payload.last_name is not None:
        updates["last_name"] = payload.last_name
    if payload.gender is not None:
        updates["gender"] = payload.gender
    if payload.photo_url is not None:
        updates["photo_url"] = payload.photo_url
    if payload.extras is not None:
        updates["extras"] = payload.extras
    merged = await update_persona_fields(uid, updates)

    # Trigger a background trip generation so the Itinerary tab is populated
    # immediately after onboarding completes (fires-and-forgets, never blocks).
    if payload.preferred_destination:
        background_tasks.add_task(_auto_generate_trip, uid, merged)

    return _persona_to_dict(merged)


@router.delete("/user/{uid}/persona")
async def delete_persona_route(
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, bool]:
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot delete another user's persona.",
        )
    deleted = await delete_persona(uid)
    return {"deleted": deleted}


# ── REST: trips ──────────────────────────────────────────────────────────────
@router.get("/user/{uid}/trips/initial")
async def get_initial_trip(
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Fetch the auto-generated trip that was created in the background right
    after onboarding completion. Returns an empty payload if the document
    doesn't exist yet (still generating, or generation failed).
    """
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot access another user's trips.",
        )
    try:
        db = get_db()
        snap = db.collection("users").document(uid).collection("trips").document("initial").get()
        if not snap.exists:
            return {"found": False}
        data = snap.to_dict() or {}
        return {"found": True, **data}
    except Exception as exc:  # noqa: BLE001
        logger.error("[trips] fetch failed for uid=%s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Failed to load initial trip.")


class TripPatch(BaseModel):
    """Payload for PATCH /api/user/{uid}/trips/initial — partial updates."""

    itinerary: Optional[Dict[str, Any]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


@router.patch("/user/{uid}/trips/initial")
async def patch_initial_trip(
    payload: TripPatch,
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Partially updates the initial trip document. Used by the frontend's
    confirmation popup after a ui_trigger event to sync plan/budget changes.
    """
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot modify another user's trips.",
        )
    try:
        db = get_db()
        doc_ref = db.collection("users").document(uid).collection("trips").document("initial")
        updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.itinerary is not None:
            updates["itinerary"] = payload.itinerary
        if payload.budget_breakdown is not None:
            updates["budget_breakdown"] = payload.budget_breakdown
        if payload.message is not None:
            updates["message"] = payload.message
        doc_ref.set(updates, merge=True)
        return {"patched": True, **updates}
    except Exception as exc:  # noqa: BLE001
        logger.error("[trips] patch failed for uid=%s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Failed to update trip details.")


# ── REST: pinned messages (governorate-based recommendations) ─────────────────
@router.get("/user/{uid}/pinned")
async def get_pinned_messages(
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return pinned recommendations customized to the user's preferred governorate.
    Sources from the user's trip history and persona preferences in Firestore.
    """
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot access another user's pinned messages.",
        )
    try:
        db = get_db()
        # Get persona for governorate — stored at users/{uid}/persona/profile
        persona_snap = (
            db.collection("users")
            .document(uid)
            .collection("persona")
            .document("profile")
            .get()
        )
        persona_data = persona_snap.to_dict() if persona_snap.exists else {}
        destination = persona_data.get("preferred_destination", "Egypt")

        # Get pinned collection (if any user-pinned messages exist)
        pinned_docs = (
            db.collection("users")
            .document(uid)
            .collection("pinned")
            .order_by("created_at", direction="DESCENDING")
            .limit(10)
            .stream()
        )
        pins = [doc.to_dict() for doc in pinned_docs]

        # Also pull the initial trip summary as a default pin
        trip_snap = db.collection("users").document(uid).collection("trips").document("initial").get()
        trip_data = trip_snap.to_dict() if trip_snap.exists else None

        return {
            "destination": destination,
            "pins": pins,
            "trip_summary": trip_data.get("message") if trip_data else None,
            "itinerary_preview": trip_data.get("itinerary") if trip_data else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("[pinned] fetch failed for uid=%s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Failed to load pinned messages.")


# ── REST: chat history (session listing + message replay) ────────────────────
@router.get("/user/{uid}/sessions")
async def list_sessions(
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
    limit: int = 30,
) -> Dict[str, Any]:
    """Return a list of the user's past chat sessions (most recent first)."""
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    from services.conversation_state import list_user_sessions
    sessions = await list_user_sessions(uid, limit=min(limit, 50))
    return {"sessions": sessions}


@router.get("/user/{uid}/sessions/{sid}/messages")
async def get_session_messages_route(
    uid: str = Path(..., min_length=1),
    sid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
    limit: int = 50,
) -> Dict[str, Any]:
    """Return messages for a specific session (for chat history replay)."""
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    from services.conversation_state import get_session_messages
    messages = await get_session_messages(uid, sid, limit=min(limit, 100))
    return {"session_id": sid, "messages": messages}


class ActivityToggleRequest(BaseModel):
    """Payload for PATCH /api/user/{uid}/trips/initial/activity."""
    day_index: int
    activity_index: int
    done: bool


@router.patch("/user/{uid}/trips/initial/activity")
async def toggle_activity_route(
    payload: ActivityToggleRequest,
    uid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Atomically toggle one activity's done flag and recompute remaining_budget.
    Reads the current doc, applies the delta, writes back in a single set().
    """
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: cannot modify another user's trips.")
    try:
        db = get_db()
        doc_ref = db.collection("users").document(uid).collection("trips").document("initial")
        snap = doc_ref.get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail="Trip not found.")

        data = snap.to_dict() or {}
        itinerary = data.get("itinerary") or {}
        days = itinerary.get("days") or []
        budget = data.get("budget_breakdown") or {}

        day_idx = payload.day_index
        act_idx = payload.activity_index
        if day_idx < 0 or day_idx >= len(days):
            raise HTTPException(status_code=422, detail="day_index out of range.")
        activities = days[day_idx].get("activities") or []
        if act_idx < 0 or act_idx >= len(activities):
            raise HTTPException(status_code=422, detail="activity_index out of range.")

        activity = dict(activities[act_idx])
        cost = float(activity.get("cost") or 0)
        was_done = bool(activity.get("done", False))
        activity["done"] = payload.done

        # Recompute remaining_budget
        total_usd = budget.get("total_usd")
        remaining = budget.get("remaining_budget")
        if total_usd is not None:
            if remaining is None:
                remaining = total_usd
            if payload.done and not was_done:
                remaining = max(0, remaining - cost)
            elif not payload.done and was_done:
                remaining = min(total_usd, remaining + cost)
            budget["remaining_budget"] = remaining

        activities[act_idx] = activity
        days[day_idx]["activities"] = activities
        itinerary["days"] = days

        doc_ref.set(
            {
                "itinerary": itinerary,
                "budget_breakdown": budget,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            merge=True,
        )
        return {
            "updated": True,
            "done": payload.done,
            "remaining_budget": budget.get("remaining_budget"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[trips] toggle_activity failed for uid=%s: %s", uid, exc)
        raise HTTPException(status_code=500, detail="Failed to toggle activity.")


class SessionPatch(BaseModel):
    """Payload for PATCH /api/user/{uid}/sessions/{sid} — rename."""
    title: str


@router.patch("/user/{uid}/sessions/{sid}")
async def rename_session_route(
    payload: SessionPatch,
    uid: str = Path(..., min_length=1),
    sid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Rename a chat session."""
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    title = payload.title.strip()[:120]
    if not title:
        raise HTTPException(status_code=422, detail="title must not be blank.")
    from services.memory_service import rename_session
    ok = await rename_session(uid, sid, title)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to rename session.")
    return {"session_id": sid, "title": title, "renamed": True}


@router.delete("/user/{uid}/sessions/{sid}")
async def delete_session_route(
    uid: str = Path(..., min_length=1),
    sid: str = Path(..., min_length=1),
    current_user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete a chat session and all its messages."""
    _require_firebase()
    if uid != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    from services.memory_service import delete_session
    ok = await delete_session(uid, sid)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete session.")
    return {"session_id": sid, "deleted": True}


# ── WebSocket: connection tracking & limits ───────────────────────────────────
_ws_connections: Dict[str, int] = collections.defaultdict(int)
_WS_MAX_CONNECTIONS_PER_USER = 5
_WS_IDLE_TIMEOUT_SEC = 300  # 5 minutes idle → disconnect
_WS_MESSAGE_MAX_SIZE = 65536  # 64KB max message payload
_WS_RATE_LIMIT_MESSAGES = 10  # max messages per window
_WS_RATE_LIMIT_WINDOW_SEC = 30  # window size in seconds


# ── WebSocket: streaming chat ─────────────────────────────────────────────────
@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket) -> None:
    """
    Streaming chat WebSocket — Touri Offline RAG Mode.

    Path A (multimodal OR plain text): streams tokens directly from
    ``stream_gemini_chat`` via native ``generate_content_async(stream=True)``.

    Path B (LangGraph workflow): the rich itinerary + budget + concierge
    agents powered by Gemma-4-26B-A4B-IT with 100% ChromaDB RAG grounding.
    Tokens are re-streamed word-by-word for a smooth ChatGPT typing effect.
    """
    # SECURITY: Authenticate BEFORE accepting the WebSocket connection.
    # Accept token from (in priority order):
    #   1. HttpOnly cookie (web)
    #   2. Authorization header (mobile Bearer)
    #   3. ?token= query param (Expo mobile — cannot set headers on WS)
    token = websocket.cookies.get("touri_access")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(None, 1)[1].strip()
    if not token:
        token = websocket.query_params.get("token") or None

    authenticated_uid = None
    if token:
        authenticated_uid = decode_access_token(token)

    if not authenticated_uid:
        logger.warning("[ws] connection rejected BEFORE accept: authentication failed")
        await websocket.close(code=4001)
        return

    # Enforce per-user connection limits
    if _ws_connections[authenticated_uid] >= _WS_MAX_CONNECTIONS_PER_USER:
        logger.warning("[ws] connection rejected: user %s exceeded max connections", authenticated_uid)
        await websocket.close(code=4008)
        return

    await websocket.accept()
    _ws_connections[authenticated_uid] += 1
    logger.info("[ws] client connected (uid=%s, active=%d)", authenticated_uid, _ws_connections[authenticated_uid])
    # Rate limiting state for this connection
    _msg_timestamps: List[float] = []

    try:
        while True:
            # Idle timeout: disconnect if no message received within window
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=_WS_IDLE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.info("[ws] idle timeout for uid=%s, disconnecting", authenticated_uid)
                await websocket.send_json({"type": "error", "message": "Connection timed out due to inactivity."})
                await websocket.close(code=4000)
                return

            # Payload size limit
            if len(data) > _WS_MESSAGE_MAX_SIZE:
                await websocket.send_json({"type": "error", "message": "Message payload too large."})
                continue

            # Rate limiting: sliding window
            now = time.time()
            _msg_timestamps = [ts for ts in _msg_timestamps if now - ts < _WS_RATE_LIMIT_WINDOW_SEC]
            if len(_msg_timestamps) >= _WS_RATE_LIMIT_MESSAGES:
                await websocket.send_json({
                    "type": "error",
                    "message": "Rate limit exceeded. Please slow down.",
                    "retry_after": _WS_RATE_LIMIT_WINDOW_SEC,
                })
                continue
            _msg_timestamps.append(now)

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                continue

            user_id = authenticated_uid
            # SECURITY: Strip any UI_TRIGGER injection from user messages
            message = strip_user_triggers(str(payload.get("message") or "")).strip()
            language = payload.get("language") or "en"
            language = language if language in ("en", "ar") else "en"
            session_id = str(payload.get("session_id") or uuid.uuid4())
            history_raw = payload.get("history") or []
            parts_raw = payload.get("parts") or []
            is_multimodal = (
                payload.get("type") == "multimodal" or bool(parts_raw)
            )
            # Allow the client to opt-in / out of LangGraph for plain text turns.
            use_graph = bool(payload.get("use_graph", False))

            if not message and not parts_raw:
                await websocket.send_json(
                    {"type": "error", "message": "message (or parts) are required."}
                )
                continue

            if len(message) > 10000:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Message exceeds maximum allowed length of 10,000 characters.",
                    }
                )
                continue

            total_attachment_bytes = sum(len(p.get("data") or "") for p in parts_raw)
            if total_attachment_bytes > 20_000_000:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Attachments exceed maximum allowed size limit of 15MB.",
                    }
                )
                continue


            await websocket.send_json(
                {"type": "status", "phase": "thinking", "session_id": session_id}
            )

            # ── Path A: native Mistral streaming (multimodal OR fast text) ──
            if is_multimodal or not use_graph:
                response_text = ""
                trace_steps: List[Dict[str, Any]] = []
                final_payload: Optional[Dict[str, Any]] = None

                await websocket.send_json(
                    {"type": "status", "phase": "streaming", "agent": "Mistral"}
                )

                try:
                    async for evt in stream_mistral_chat(
                        user_id=user_id,
                        session_id=session_id,
                        text=message,
                        parts=parts_raw,
                        language=language,
                        enable_tools=True,
                    ):
                        kind = evt.get("type")
                        if kind == "token":
                            response_text += evt["content"]
                            await websocket.send_json(
                                {"type": "token", "content": evt["content"]}
                            )
                        elif kind == "trace":
                            trace_steps.append(evt["step"])
                            await websocket.send_json(
                                {"type": "trace", "step": evt["step"]}
                            )
                        elif kind == "final":
                            final_payload = evt
                except Exception as exc:  # noqa: BLE001
                    logger.error("[ws] mistral stream failed: %s", exc, exc_info=True)
                    await websocket.send_json({"type": "error", "message": "Failed to generate response. Please try again."})
                    continue

                final_text = sanitize_output((final_payload or {}).get("text") or response_text)
                await websocket.send_json(
                    {
                        "type": "final",
                        "session_id": session_id,
                        "message": final_text,
                        "agent": (final_payload or {}).get("agent", "Mistral"),
                        "intent": (final_payload or {}).get("intent", "general"),
                        "language": language,
                        "agent_trace": sanitize_agent_trace(trace_steps),
                        "itinerary": None,
                        "budget_breakdown": None,
                        "spots_json": None,
                        "suggestions": [],
                        "structured_questions": None,
                    }
                )
                continue

            # ── Path B: full LangGraph workflow with live streaming ─────────
            # Wrap in a Task so WebSocketDisconnect mid-stream can cancel it,
            # preventing wasted LLM token spend on abandoned clients.
            all_trace: List[Dict[str, Any]] = []
            final_state: Dict[str, Any] = {}

            async def _run_graph_stream() -> None:
                async for evt in stream_chat(
                    user_id=user_id,
                    session_id=session_id,
                    user_message=message,
                    language=language,
                    chat_history=history_raw,
                ):
                    evt_type = evt.get("type")
                    if evt_type == "node_start":
                        await websocket.send_json(
                            {
                                "type": "status",
                                "phase": "streaming",
                                "agent": evt.get("label", ""),
                                "status_msg": evt.get("status_msg", ""),
                                "node": evt.get("node", ""),
                            }
                        )
                    elif evt_type == "trace":
                        step = evt.get("step", {})
                        all_trace.append(step)
                        await websocket.send_json({"type": "trace", "step": step})
                    elif evt_type == "node_end":
                        final_state.update(evt.get("state", {}))
                    elif evt_type == "final":
                        final_state.update(evt.get("state", {}))

            graph_task = asyncio.create_task(_run_graph_stream())
            try:
                await graph_task
            except asyncio.CancelledError:
                logger.info("[ws] graph task cancelled mid-stream (uid=%s)", user_id)
                raise  # re-raise → caught by outer WebSocketDisconnect handler
            except WebSocketDisconnect:
                graph_task.cancel()
                try:
                    await graph_task
                except (asyncio.CancelledError, Exception):
                    pass
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("[ws] graph stream failed: %s", exc, exc_info=True)
                try:
                    await websocket.send_json({"type": "error", "message": "Failed to generate response. Please try again."})
                except Exception:
                    pass
                continue

            # Re-stream the response text token-by-token for smooth UI
            response_text = clean_response(final_state.get("response_text", "") or "")
            visible_text = response_text
            ui_trigger_block = ""
            if response_text:
                # SECURITY: Validate UI_TRIGGER blocks via schema validation
                visible_text, validated_triggers = extract_and_validate_triggers(response_text)
                visible_text = sanitize_output(visible_text)
                # Reconstruct safe trigger block only from validated triggers
                ui_trigger_block = ""
                if validated_triggers:
                    import json as _json
                    trigger_data = validated_triggers[0].model_dump(exclude_none=True)
                    ui_trigger_block = f"---UI_TRIGGER---\n{_json.dumps(trigger_data)}\n---"

                try:
                    words = re.split(r"(\s+)", visible_text)
                    first = True
                    for word in words:
                        if not word:
                            continue
                        await websocket.send_json(
                            {"type": "token", "content": word}
                        )
                        if first:
                            first = False
                        else:
                            await asyncio.sleep(0.008)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[ws] local echo stream failed (%s) — sending full reply.",
                        exc,
                    )
                    await websocket.send_json(
                        {"type": "token", "content": visible_text}
                    )

            # Build final sanitized response
            final_message = f"{visible_text}\n\n{ui_trigger_block}".strip() if ui_trigger_block else visible_text
            await websocket.send_json(
                {
                    "type": "final",
                    "session_id": session_id,
                    "message": final_message,
                    "agent": final_state.get("active_agent"),
                    "intent": final_state.get("intent"),
                    "language": final_state.get("language", language),
                    "agent_trace": sanitize_agent_trace(all_trace),
                    "itinerary": final_state.get("itinerary"),
                    "budget_breakdown": final_state.get("budget_breakdown"),
                    "spots_json": final_state.get("spots_json"),
                    "suggestions": final_state.get("suggestions", []),
                    "structured_questions": final_state.get("structured_questions"),
                    "conversation_state": final_state.get("conversation_state"),
                    "requirements_status": final_state.get("requirements_status"),
                }
            )
    except WebSocketDisconnect:
        logger.info("[ws] client disconnected (uid=%s)", authenticated_uid)
    except Exception as exc:  # noqa: BLE001
        logger.error("[ws] unexpected error: %s", exc, exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        # Always decrement connection counter
        _ws_connections[authenticated_uid] = max(0, _ws_connections[authenticated_uid] - 1)
