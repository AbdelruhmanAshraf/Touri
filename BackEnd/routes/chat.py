"""
Phase 2 chat routes.

Surfaces:
    POST /api/chat                              — single-shot REST chat
    GET  /api/user/{uid}/persona                — read persona from Firestore
    POST /api/user/{uid}/persona                — overwrite / patch persona
    WS   /api/chat/ws                           — streaming chat with live agent_trace
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.gemini_chat import run_multimodal_chat, stream_gemini_chat
from agents.graph import run_chat, stream_chat
from agents.llm import FAST_MODEL, get_llm, lang_directive
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
    data: str = Field(..., description="Base64-encoded blob (no data: prefix).")


class ChatRequest(BaseModel):
    user_id: str
    message: str
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
    suggestions: List[str] = []


class PersonaWrite(BaseModel):
    """Payload accepted by POST /api/user/{uid}/persona."""

    preferred_destination: Optional[str] = None
    tourism_type: Optional[str] = Field(default=None, pattern=r"^(leisure|medical)$")
    party_size: Optional[int] = Field(default=None, ge=1, le=20)
    budget_bracket: Optional[str] = Field(
        default=None, pattern=r"^(economy|mid_range|luxury)$"
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
        "tourism_type": p.tourism_type.value,
        "party_size": p.party_size,
        "budget_bracket": p.budget_bracket.value,
        "extras": p.extras,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── REST: chat ────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
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
            raise HTTPException(status_code=500, detail=str(exc))
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
            raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(
        session_id=session_id,
        message=state.get("response_text", ""),
        agent=state.get("active_agent", "Travel Planner"),
        intent=state.get("intent", "general"),
        language=state.get("language", req.language),
        agent_trace=state.get("agent_trace", []),
        itinerary=state.get("itinerary"),
        budget_breakdown=state.get("budget_breakdown"),
        suggestions=state.get("suggestions", []),
    )


# ── REST: persona CRUD ───────────────────────────────────────────────────────
@router.get("/user/{uid}/persona")
async def get_persona_route(uid: str = Path(..., min_length=1)) -> Dict[str, Any]:
    _require_firebase()
    persona = await get_or_create_persona(uid)
    return _persona_to_dict(persona)


@router.post("/user/{uid}/persona")
async def upsert_persona_route(
    payload: PersonaWrite,
    background_tasks: BackgroundTasks,
    uid: str = Path(..., min_length=1),
) -> Dict[str, Any]:
    _require_firebase()
    updates: Dict[str, Any] = {}
    if payload.preferred_destination is not None:
        updates["preferred_destination"] = payload.preferred_destination
    if payload.tourism_type is not None:
        updates["tourism_type"] = TourismType(payload.tourism_type)
    if payload.party_size is not None:
        updates["party_size"] = payload.party_size
    if payload.budget_bracket is not None:
        updates["budget_bracket"] = BudgetBracket(payload.budget_bracket)
    if payload.extras is not None:
        updates["extras"] = payload.extras
    merged = await update_persona_fields(uid, updates)

    # Trigger a background trip generation so the Itinerary tab is populated
    # immediately after onboarding completes (fires-and-forgets, never blocks).
    if payload.preferred_destination:
        background_tasks.add_task(_auto_generate_trip, uid, merged)

    return _persona_to_dict(merged)


@router.delete("/user/{uid}/persona")
async def delete_persona_route(uid: str = Path(..., min_length=1)) -> Dict[str, bool]:
    _require_firebase()
    deleted = await delete_persona(uid)
    return {"deleted": deleted}


# ── REST: trips ──────────────────────────────────────────────────────────────
@router.get("/user/{uid}/trips/initial")
async def get_initial_trip(uid: str = Path(..., min_length=1)) -> Dict[str, Any]:
    """
    Fetch the auto-generated trip that was created in the background right
    after onboarding completion. Returns an empty payload if the document
    doesn't exist yet (still generating, or generation failed).
    """
    _require_firebase()
    try:
        db = get_db()
        snap = db.collection("users").document(uid).collection("trips").document("initial").get()
        if not snap.exists:
            return {"found": False}
        data = snap.to_dict() or {}
        return {"found": True, **data}
    except Exception as exc:  # noqa: BLE001
        logger.error("[trips] fetch failed for uid=%s: %s", uid, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket: streaming chat ─────────────────────────────────────────────────
@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket) -> None:
    """
    Streaming chat WebSocket — Phase 4 native Gemini SDK pipeline.

    Path A (multimodal OR plain text): we stream tokens directly out of
    ``stream_gemini_chat``, which calls
    ``model.generate_content_async(stream=True)`` natively against
    ``gemini-2.5-flash`` (Gemma cannot do multimodal/tool-calling).

    Path B (legacy LangGraph workflow): retained for the rich itinerary +
    budget agents. The structured output is still streamed back to the UI so
    the typing animation stays smooth, but tokens come from Gemini's native
    stream rather than a LangChain echo step.
    """
    await websocket.accept()
    logger.info("[ws] client connected")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                continue

            user_id = str(payload.get("user_id") or "").strip()
            message = str(payload.get("message") or "").strip()
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

            if not user_id or (not message and not parts_raw):
                await websocket.send_json(
                    {"type": "error", "message": "user_id and message (or parts) are required."}
                )
                continue

            await websocket.send_json(
                {"type": "status", "phase": "thinking", "session_id": session_id}
            )

            # ── Path A: native Gemini streaming (multimodal OR fast text) ──
            if is_multimodal or not use_graph:
                response_text = ""
                trace_steps: List[Dict[str, Any]] = []
                final_payload: Optional[Dict[str, Any]] = None

                await websocket.send_json(
                    {"type": "status", "phase": "streaming", "agent": "Gemini"}
                )

                try:
                    async for evt in stream_gemini_chat(
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
                    logger.error("[ws] gemini stream failed: %s", exc, exc_info=True)
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue

                final_text = (final_payload or {}).get("text") or response_text
                await websocket.send_json(
                    {
                        "type": "final",
                        "session_id": session_id,
                        "message": final_text,
                        "agent": (final_payload or {}).get("agent", "Gemini"),
                        "intent": (final_payload or {}).get("intent", "general"),
                        "language": language,
                        "agent_trace": trace_steps,
                        "itinerary": None,
                        "budget_breakdown": None,
                        "suggestions": [],
                    }
                )
                continue

            # ── Path B: full LangGraph workflow with live streaming ─────────
            try:
                all_trace: List[Dict[str, Any]] = []
                final_state: Dict[str, Any] = {}

                async for evt in stream_chat(
                    user_id=user_id,
                    session_id=session_id,
                    user_message=message,
                    language=language,
                    chat_history=history_raw,
                ):
                    evt_type = evt.get("type")

                    if evt_type == "node_start":
                        # Stream the active agent node label to the UI
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
                        node_state = evt.get("state", {})
                        final_state.update(node_state)

                    elif evt_type == "final":
                        final_state.update(evt.get("state", {}))

            except Exception as exc:  # noqa: BLE001
                logger.error("[ws] graph stream failed: %s", exc, exc_info=True)
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            # Re-stream the response text token-by-token for smooth UI
            response_text = final_state.get("response_text", "") or ""
            if response_text:
                echo_prompt = (
                    "Repeat the following text verbatim, preserving wording "
                    "and line breaks. Do not add commentary.\n\n" + response_text
                )
                try:
                    async for evt in stream_gemini_chat(
                        user_id=user_id,
                        session_id=session_id,
                        text=echo_prompt,
                        parts=None,
                        language=language,
                        enable_tools=False,
                    ):
                        if evt.get("type") == "token":
                            await websocket.send_json(
                                {"type": "token", "content": evt["content"]}
                            )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[ws] native echo stream failed (%s) — sending full reply.",
                        exc,
                    )
                    await websocket.send_json(
                        {"type": "token", "content": response_text}
                    )

            await websocket.send_json(
                {
                    "type": "final",
                    "session_id": session_id,
                    "message": response_text,
                    "agent": final_state.get("active_agent"),
                    "intent": final_state.get("intent"),
                    "language": final_state.get("language", language),
                    "agent_trace": all_trace,
                    "itinerary": final_state.get("itinerary"),
                    "budget_breakdown": final_state.get("budget_breakdown"),
                    "suggestions": final_state.get("suggestions", []),
                }
            )
    except WebSocketDisconnect:
        logger.info("[ws] client disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.error("[ws] unexpected error: %s", exc, exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
