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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.graph import run_chat
from agents.llm import FAST_MODEL, get_llm, lang_directive
from agents.state import AgentStep, ChatMessage, fresh_state
from memory.firebase_client import is_ready as firebase_ready
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
class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None
    language: str = Field(default="en", pattern=r"^(en|ar)$")
    history: List[ChatMessage] = Field(default_factory=list)


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
    payload: PersonaWrite, uid: str = Path(..., min_length=1)
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
    return _persona_to_dict(merged)


@router.delete("/user/{uid}/persona")
async def delete_persona_route(uid: str = Path(..., min_length=1)) -> Dict[str, bool]:
    _require_firebase()
    deleted = await delete_persona(uid)
    return {"deleted": deleted}


# ── WebSocket: streaming chat ─────────────────────────────────────────────────
async def _stream_final_message(
    websocket: WebSocket, language: str, response_text: str
) -> None:
    """
    Re-stream the agent's finalised reply token-by-token through Gemini.

    The LangGraph agents return a fully composed ``response_text``; for the
    mobile UI we want the *appearance* of token streaming. We feed the reply
    back through Gemini with a one-shot "echo this" instruction so the
    frontend receives small chunks in real time.
    """
    if not response_text:
        return
    llm = get_llm(model=FAST_MODEL, streaming=True, temperature=0.0)
    echo_prompt = (
        "Repeat the following text exactly, preserving wording, formatting "
        "and line breaks. Do not add commentary.\n\n" + response_text
    )
    try:
        async for chunk in llm.astream(
            [
                SystemMessage(content=lang_directive(language)),
                HumanMessage(content=echo_prompt),
            ]
        ):
            token = getattr(chunk, "content", "") or ""
            if token:
                await websocket.send_json({"type": "token", "content": token})
    except Exception as exc:  # noqa: BLE001
        # If streaming fails for any reason, deliver the full text in one shot.
        logger.warning("[ws] token stream failed (%s) — sending full reply.", exc)
        await websocket.send_json({"type": "token", "content": response_text})


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket) -> None:
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
            session_id = str(payload.get("session_id") or uuid.uuid4())
            history_raw = payload.get("history") or []

            if not user_id or not message:
                await websocket.send_json(
                    {"type": "error", "message": "user_id and message are required."}
                )
                continue

            await websocket.send_json(
                {
                    "type": "status",
                    "phase": "thinking",
                    "session_id": session_id,
                }
            )

            try:
                state = await run_chat(
                    user_id=user_id,
                    session_id=session_id,
                    user_message=message,
                    language=language if language in ("en", "ar") else "en",
                    chat_history=history_raw,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[ws] graph failed: %s", exc, exc_info=True)
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            # Replay agent_trace steps so the UI can animate the audit panel.
            for step in state.get("agent_trace", []):
                await websocket.send_json({"type": "trace", "step": step})

            # Stream the response text token-by-token.
            await websocket.send_json(
                {
                    "type": "status",
                    "phase": "streaming",
                    "agent": state.get("active_agent"),
                    "intent": state.get("intent"),
                }
            )
            await _stream_final_message(
                websocket,
                language=state.get("language", language),
                response_text=state.get("response_text", ""),
            )

            # Final structured payload (so the UI has the full ChatResponse).
            await websocket.send_json(
                {
                    "type": "final",
                    "session_id": session_id,
                    "message": state.get("response_text", ""),
                    "agent": state.get("active_agent"),
                    "intent": state.get("intent"),
                    "language": state.get("language"),
                    "agent_trace": state.get("agent_trace", []),
                    "itinerary": state.get("itinerary"),
                    "budget_breakdown": state.get("budget_breakdown"),
                    "suggestions": state.get("suggestions", []),
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
