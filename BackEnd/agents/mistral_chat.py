"""
Native Mistral chat handler — streaming + vision + function calling.

Exposes `stream_mistral_chat` which matches the signature of stream_gemini_chat.
"""

from __future__ import annotations

import base64
import json
import io
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

# Try to import pypdf for local PDF text extraction
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from agents.tools import TOOL_DECLARATIONS, execute_tool
from agents.llm import get_mistral_client, lang_directive, GLOBAL_SYSTEM_INSTRUCTION
from agents.state import make_step
from config import settings

logger = logging.getLogger(__name__)

# Primary models for Mistral AI
MISTRAL_TEXT_MODEL = "mistral-large-latest"
MISTRAL_VISION_MODEL = "pixtral-12b-latest"  # Pixtral is vision-capable

SUPPORTED_IMAGE_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
}


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text pages from PDF bytes using pypdf."""
    if PdfReader is None:
        logger.warning("[mistral_chat] pypdf library is not installed. Cannot parse PDF.")
        return ""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_parts.append(f"--- Page {i+1} ---\n{text}")
        return "\n".join(text_parts).strip()
    except Exception as exc:
        logger.warning("[mistral_chat] PDF extraction failed: %s", exc)
        return ""


async def stream_mistral_chat(
    *,
    user_id: str,
    session_id: str,
    text: str,
    parts: Optional[List[Dict[str, str]]] = None,
    language: str = "en",
    enable_tools: bool = True,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream a chat reply from Mistral AI token-by-token.
    Matches the exact output contracts and events of the legacy gemini handler.
    """
    client = get_mistral_client()

    content_list: List[Dict[str, Any]] = []
    pdf_texts: List[str] = []
    has_images = False

    # ── Process parts (images, PDF documents, etc.) ──
    for raw in parts or []:
        mime = (raw.get("mime_type") or "").lower()
        data = raw.get("data") or ""
        filename = raw.get("filename") or "attachment"
        if not data:
            continue

        try:
            blob = base64.b64decode(data, validate=False)
        except Exception as exc:
            logger.warning("[mistral] base64 decode failed for part %s: %s", mime, exc)
            continue

        if mime in SUPPORTED_IMAGE_MIME:
            has_images = True
            # Mistral expects images as standard base64 data URIs
            data_url = f"data:{mime};base64,{data}"
            content_list.append({
                "type": "image_url",
                "image_url": data_url
            })
        elif mime == "application/pdf":
            pdf_text = extract_text_from_pdf(blob)
            if pdf_text:
                pdf_texts.append(f"\n[Attached PDF: {filename}]\n{pdf_text}\n")
        else:
            logger.warning("[mistral] dropping unsupported input part type: %s", mime)

    # Choose model
    model_name = MISTRAL_VISION_MODEL if has_images else settings.MISTRAL_PRO_MODEL

    # Construct the user text input, appending any extracted PDF texts
    user_text = text or "Describe and analyse the attached media."
    if pdf_texts:
        user_text += "\n" + "\n".join(pdf_texts)

    # Insert user text as the first element in user content
    content_list.insert(0, {"type": "text", "text": user_text})

    # Wrap TOOL_DECLARATIONS into Mistral format
    mistral_tools = [
        {"type": "function", "function": tool}
        for tool in TOOL_DECLARATIONS
    ] if (enable_tools and TOOL_DECLARATIONS) else None

    # Construct complete chat history payload
    messages = [
        {"role": "system", "content": GLOBAL_SYSTEM_INSTRUCTION + "\n" + lang_directive(language)},
        {"role": "user", "content": content_list}
    ]

    yield {
        "type": "trace",
        "step": make_step(
            agent="Mistral",
            action="chat_complete_async",
            tool="mistral",
            reasoning=(
                f"model={model_name} has_images={has_images} "
                f"pdf_attachments={len(pdf_texts)} tools_enabled={enable_tools}"
            ),
        ),
    }

    max_tool_rounds = 4
    final_text_accum = ""

    for round_idx in range(max_tool_rounds + 1):
        try:
            # We call standard chat completion to inspect if the model wants to call tools.
            # Mistral tool calling works best with non-streaming calls for parsing parameters.
            response = await client.chat.complete_async(
                model=model_name,
                messages=messages,
                tools=mistral_tools if round_idx < max_tool_rounds else None,
            )
        except Exception as exc:
            logger.error("[mistral] completion round %d failed: %s", round_idx, exc, exc_info=True)
            yield {
                "type": "final",
                "text": (
                    "Sorry, I couldn't reach the Mistral language model right now. "
                    "Please try again in a moment."
                ),
                "agent": "Mistral",
                "language": language,
                "agent_trace": [
                    make_step(
                        agent="Mistral",
                        action="error",
                        tool="mistral",
                        reasoning=str(exc),
                    ),
                ],
                "error": str(exc),
            }
            return

        choice = response.choices[0]
        message_obj = choice.message
        tool_calls = getattr(message_obj, "tool_calls", None)

        if tool_calls:
            # Model decided to run one or more tools. 
            # 1. Append the model's tool calls turn to the conversation history.
            messages.append({
                "role": "assistant",
                "content": message_obj.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    } for tc in tool_calls
                ]
            })

            # 2. Execute each tool and append the output to the history.
            for tc in tool_calls:
                name = tc.function.name
                raw_args = tc.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                yield {
                    "type": "trace",
                    "step": make_step(
                        agent="Mistral",
                        action="tool_execute",
                        tool=name,
                        reasoning=f"arguments={args}",
                    ),
                }

                try:
                    result = await execute_tool(name, args)
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as e:
                    logger.warning("[mistral] tool %s failed: %s", name, e)
                    result_str = f"Error: {e}"

                messages.append({
                    "role": "tool",
                    "name": name,
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
            
            # Loop for the next round using updated history
            continue

        else:
            # No tool calls! This is the final text response.
            # We can now stream this final text response to the client.
            # We already have the full text from the completion response: message_obj.content.
            # To preserve the live typing experience on the frontend, we use client.chat.stream_async
            # on the exact same conversation history (with tools disabled to prevent re-routing).
            final_text_accum = message_obj.content or ""
            
            try:
                response_stream = await client.chat.stream_async(
                    model=model_name,
                    messages=messages,
                )
                async for chunk in response_stream:
                    delta = chunk.data.choices[0].delta
                    content = delta.content
                    if content:
                        yield {"type": "token", "content": content}
            except Exception as exc:
                # Fallback: yield the already fetched complete text as a single token chunk
                logger.warning("[mistral] fallback from streaming to batch: %s", exc)
                yield {"type": "token", "content": final_text_accum}
            
            break

    yield {
        "type": "final",
        "text": final_text_accum,
        "agent": "Mistral",
        "language": language,
        "agent_trace": [],
    }


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

    async for evt in stream_mistral_chat(
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
        "active_agent": final_evt.get("agent", "Mistral"),
        "intent": final_evt.get("intent", "general"),
        "language": final_evt.get("language", language),
        "agent_trace": trace + (final_evt.get("agent_trace") or []),
        "suggestions": [],
    }


__all__ = [
    "run_multimodal_chat",
    "stream_mistral_chat",
]
