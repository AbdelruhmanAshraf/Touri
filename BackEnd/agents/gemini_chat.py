"""
Native Gemini chat handler — streaming + multimodal + function calling.

This module is the primary chat backend after the Phase 4 migration. It uses
the ``google.generativeai`` SDK directly so we get:

  * **Native token streaming** via ``generate_content_async(stream=True)``.
  * **Multimodal byte ingestion** (image / audio / PDF) without local OCR.
  * **Function calling** — the four strategic Touri tools declared in
    ``agents/gemini_tools.py``.

Model split:
  * Multimodal & tool-calling chats → ``MULTIMODAL_MODEL`` (gemini-2.5-flash).
    Required because Google's Gemma family is text-only and does not support
    inline_data parts or function_declarations.
  * Plain text chats → ``settings.GEMINI_FAST_MODEL`` (defaults to the user's
    ``gemma-4-26b-a4b-it`` in .env, fallback gemini-2.5-flash if Gemma fails).

The handler exposes a single async generator ``stream_gemini_chat`` that
yields a tagged stream of events:

    {"type": "trace",  "step": {...}}
    {"type": "token",  "content": "word "}
    {"type": "final",  "text": "...full response..."}

Callers (the FastAPI WebSocket route) just forward each event over the wire.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from agents.gemini_tools import TOOL_DECLARATIONS, execute_tool
from agents.llm import lang_directive
from agents.state import make_step
from config import settings

logger = logging.getLogger(__name__)


# ── Models ────────────────────────────────────────────────────────────────────
# Multimodal + tool calling REQUIRE a Gemini model (Gemma is text-only).
MULTIMODAL_MODEL = "gemini-2.5-flash"

SUPPORTED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "audio/mp3", "audio/mpeg", "audio/wav", "audio/m4a", "audio/aac",
    "audio/ogg", "audio/flac",
    "application/pdf",
    "video/mp4", "video/mov", "video/avi", "video/webm",
}


def _decode_parts(parts: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Validate + decode incoming base64 parts into google-genai inline_data."""
    decoded: List[Dict[str, Any]] = []
    for raw in parts or []:
        mime = (raw.get("mime_type") or "").lower()
        data = raw.get("data") or ""
        if mime not in SUPPORTED_MIME:
            logger.warning("[multimodal] dropping unsupported part: %s", mime)
            continue
        try:
            blob = base64.b64decode(data, validate=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[multimodal] base64 decode failed for %s: %s", mime, exc)
            continue
        if not blob:
            continue
        decoded.append({"inline_data": {"mime_type": mime, "data": blob}})
    return decoded


def _configure_genai() -> Any:
    """Import + configure ``google.generativeai`` with the active API key."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        ) from exc
    genai.configure(api_key=api_key)
    return genai


def _build_tool_config(genai: Any) -> Any:
    """Wrap TOOL_DECLARATIONS in the SDK's Tool/FunctionDeclaration objects."""
    try:
        # google-generativeai accepts either dicts or typed protos.
        return [{"function_declarations": TOOL_DECLARATIONS}]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[multimodal] tool config build failed: %s", exc)
        return None


async def stream_gemini_chat(
    *,
    user_id: str,
    session_id: str,
    text: str,
    parts: Optional[List[Dict[str, str]]] = None,
    language: str = "en",
    enable_tools: bool = True,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream a chat reply from Gemini — natively, token by token.

    Yields a sequence of ``{"type": ..., ...}`` events. The final yield is
    always ``{"type": "final", ...}`` carrying the complete response shape.
    """
    genai = _configure_genai()
    inline_parts = _decode_parts(parts or [])
    has_attachments = bool(inline_parts)

    # Multimodal/tool-calling MUST run on a Gemini model.
    model_name = (
        MULTIMODAL_MODEL
        if has_attachments or enable_tools
        else (settings.GEMINI_FAST_MODEL or MULTIMODAL_MODEL)
    )

    tools_payload = _build_tool_config(genai) if enable_tools else None

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=lang_directive(language),
            tools=tools_payload,
        )
    except Exception as exc:  # noqa: BLE001
        # Gemma rejects ``tools`` — retry without function calling.
        logger.warning("[gemini] model init with tools failed (%s) — retrying tools-off", exc)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=lang_directive(language),
        )
        tools_payload = None

    user_content: List[Any] = [{"text": text or "Describe and analyse the attached media."}]
    user_content.extend(inline_parts)

    yield {
        "type": "trace",
        "step": make_step(
            agent="Gemini",
            action="generate_content_async",
            tool="gemini",
            reasoning=(
                f"model={model_name} attachments={len(inline_parts)} "
                f"tools_enabled={tools_payload is not None}"
            ),
        ),
    }

    # ── Conversation loop: handle tool calls until the model returns text ───
    contents: List[Any] = [{"role": "user", "parts": user_content}]
    final_text_parts: List[str] = []
    max_tool_rounds = 4

    for round_idx in range(max_tool_rounds + 1):
        try:
            response_stream = await model.generate_content_async(
                contents, stream=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[gemini] stream call failed: %s", exc, exc_info=True)
            yield {
                "type": "final",
                "text": (
                    "Sorry, I couldn't reach the language model right now. "
                    "Please try again in a moment."
                ),
                "agent": "Gemini",
                "language": language,
                "agent_trace": [
                    make_step(
                        agent="Gemini",
                        action="error",
                        tool="gemini",
                        reasoning=str(exc),
                    ),
                ],
                "error": str(exc),
            }
            return

        # Buffer tool calls discovered mid-stream so we can run them after.
        pending_tool_calls: List[Dict[str, Any]] = []
        round_text_parts: List[str] = []
        full_response = None

        async for chunk in response_stream:
            full_response = chunk  # last chunk holds the aggregate

            # Token streaming — pull plain text out of each candidate chunk.
            try:
                token = chunk.text  # type: ignore[attr-defined]
            except Exception:
                token = ""
            if token:
                round_text_parts.append(token)
                yield {"type": "token", "content": token}

            # Function calls arrive on candidate.content.parts[*].function_call
            for cand in getattr(chunk, "candidates", None) or []:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", None) or []:
                    fcall = getattr(part, "function_call", None)
                    if fcall and getattr(fcall, "name", None):
                        try:
                            args = dict(fcall.args) if fcall.args else {}
                        except Exception:
                            args = {}
                        pending_tool_calls.append({"name": fcall.name, "args": args})

        # If no tool calls, this round is the final answer.
        if not pending_tool_calls:
            final_text_parts.extend(round_text_parts)
            break

        # Otherwise: execute each tool, feed responses back as a function
        # response part, and loop for another round.
        if round_idx == max_tool_rounds:
            yield {
                "type": "trace",
                "step": make_step(
                    agent="Gemini",
                    action="tool_loop_capped",
                    reasoning=f"reached cap of {max_tool_rounds} tool rounds",
                ),
            }
            break

        # Add the model's tool-call turn into the conversation history.
        if full_response is not None:
            try:
                model_parts = []
                cands = getattr(full_response, "candidates", None) or []
                if cands:
                    parts = getattr(cands[0].content, "parts", None) or []
                    for p in parts:
                        if getattr(p, "function_call", None):
                            model_parts.append(p)
                if model_parts:
                    contents.append({"role": "model", "parts": model_parts})
            except Exception:
                pass

        function_response_parts: List[Dict[str, Any]] = []
        for call in pending_tool_calls:
            yield {
                "type": "trace",
                "step": make_step(
                    agent="Gemini",
                    action=f"tool.{call['name']}",
                    tool=call["name"],
                    reasoning=f"args={json.dumps(call['args'], ensure_ascii=False)[:300]}",
                ),
            }
            tool_result = await execute_tool(call["name"], call["args"], user_id=user_id)
            function_response_parts.append({
                "function_response": {
                    "name": call["name"],
                    "response": tool_result,
                },
            })
            yield {
                "type": "trace",
                "step": make_step(
                    agent="Gemini",
                    action=f"tool.{call['name']}.result",
                    tool=call["name"],
                    reasoning=("ok=True" if tool_result.get("ok") else f"ok=False {tool_result.get('error','')}"),
                    result=str(tool_result)[:400],
                ),
            }

        contents.append({"role": "user", "parts": function_response_parts})
        # Keep any text the model emitted before tool-calling.
        final_text_parts.extend(round_text_parts)

    final_text = "".join(final_text_parts).strip()
    if not final_text:
        final_text = (
            "I received your message but couldn't generate a reply. "
            "Please try rephrasing."
        )

    yield {
        "type": "final",
        "text": final_text,
        "agent": "Gemini Multimodal" if has_attachments else "Gemini",
        "intent": "multimodal" if has_attachments else "general",
        "language": language,
        "agent_trace": [
            make_step(
                agent="Gemini",
                action="stream_complete",
                tool="gemini",
                reasoning=f"model={model_name} chars={len(final_text)}",
                result=f"{len(final_text)} chars streamed",
            ),
        ],
    }


# ── Backwards-compat: one-shot wrapper used by the REST /api/chat endpoint ───
async def run_multimodal_chat(
    *,
    user_id: str,
    session_id: str,
    text: str,
    parts: List[Dict[str, str]],
    language: str = "en",
) -> Dict[str, Any]:
    """Drain the streaming generator and return an AgentState-shaped dict."""
    response_text = ""
    trace: List[Dict[str, Any]] = []
    final_evt: Optional[Dict[str, Any]] = None

    async for evt in stream_gemini_chat(
        user_id=user_id,
        session_id=session_id,
        text=text,
        parts=parts,
        language=language,
    ):
        if evt["type"] == "token":
            response_text += evt["content"]
        elif evt["type"] == "trace":
            trace.append(evt["step"])
        elif evt["type"] == "final":
            final_evt = evt

    if final_evt is None:
        final_evt = {"text": response_text, "language": language}

    return {
        "response_text": final_evt.get("text", response_text),
        "active_agent": final_evt.get("agent", "Gemini"),
        "intent": final_evt.get("intent", "general"),
        "language": final_evt.get("language", language),
        "agent_trace": trace + (final_evt.get("agent_trace") or []),
        "suggestions": [],
    }


__all__ = [
    "run_multimodal_chat",
    "stream_gemini_chat",
    "SUPPORTED_MIME",
    "MULTIMODAL_MODEL",
]
