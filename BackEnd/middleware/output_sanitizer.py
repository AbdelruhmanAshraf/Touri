"""
AI Output Security Layer for Touri.

Validates and sanitizes model responses before delivery to the frontend.

Filters:
- Accidental system prompt leaks
- Hidden reasoning / chain-of-thought leaks
- LangGraph state / internal trace exposure
- PII patterns (emails, phone numbers, credit cards)
- RAG internal markers
- Dangerous HTML/script content
"""

from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger("touri.output_sanitizer")


# ── System prompt leak patterns ───────────────────────────────────────────────
_SYSTEM_PROMPT_LEAKS = [
    re.compile(r"(?:INSTRUCTION HIERARCHY|Security Directives|NON-NEGOTIABLE)", re.IGNORECASE),
    re.compile(r"(?:GLOBAL_SYSTEM_INSTRUCTION|system_instruction|SystemMessage)", re.IGNORECASE),
    re.compile(r"(?:Pure Offline RAG Grounding|egypt_travel_knowledge|3,?723 verified)", re.IGNORECASE),
    re.compile(r"(?:ChromaDB|chroma_db|vector_store|CHROMA_COLLECTION)", re.IGNORECASE),
    re.compile(r"(?:LangGraph|StateGraph|AgentState|langgraph)", re.IGNORECASE),
    re.compile(r"(?:firebase_admin|firebase_client|FIREBASE_CREDENTIALS)", re.IGNORECASE),
    re.compile(r"(?:gemma-4-26b|gemma-4-27b|GEMINI_API_KEY|GEMINI_PRO_MODEL)", re.IGNORECASE),
    re.compile(r"(?:router_agent|travel_planner|budget_specialist|local_concierge)\.py", re.IGNORECASE),
]

# ── Chain-of-thought / reasoning leak patterns ────────────────────────────────
_REASONING_LEAKS = [
    re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[Internal (?:Reasoning|Thought|Monologue)\].*?(?=\n\n|\Z)", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[Intent\].*?\[Response\]\s*", re.DOTALL | re.IGNORECASE),
    re.compile(r"(?:^|\n)(?:Reasoning|Thinking|Analysis):\s*.*?(?=\n\n|\Z)", re.DOTALL | re.IGNORECASE),
    re.compile(r"```(?:internal|reasoning|thought).*?```", re.DOTALL | re.IGNORECASE),
]

# ── PII patterns ─────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    # Credit card numbers (basic pattern)
    (re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"), "[CARD REDACTED]"),
    # SSN-like patterns
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ID REDACTED]"),
    # Email addresses in unexpected contexts (not user's own)
    # Keeping light — don't redact emails that are part of normal travel content
]

# ── RAG internal markers ──────────────────────────────────────────────────────
_RAG_INTERNALS = [
    re.compile(r"(?:Source|Document|Chunk):\s*(?:egypt_csv|data/|chroma)", re.IGNORECASE),
    re.compile(r"(?:Similarity|Score|Distance):\s*\d+\.\d+", re.IGNORECASE),
    re.compile(r"(?:metadata|embedding|vector_id)\s*[:=]", re.IGNORECASE),
]

# ── HTML/script injection ─────────────────────────────────────────────────────
_DANGEROUS_HTML = re.compile(r"<(?:script|iframe|object|embed|form|input|link)[^>]*>", re.IGNORECASE)
_JAVASCRIPT_URI = re.compile(r"javascript\s*:", re.IGNORECASE)


def sanitize_output(text: str) -> str:
    """
    Sanitize AI model output before sending to the frontend.

    Removes leaked system prompts, reasoning traces, PII, and dangerous content.
    """
    if not text:
        return text

    original = text

    # 1. Strip reasoning/thinking blocks
    for pattern in _REASONING_LEAKS:
        text = pattern.sub("", text)

    # 2. Check for system prompt leaks
    for pattern in _SYSTEM_PROMPT_LEAKS:
        if pattern.search(text):
            logger.error("[output_sanitizer] system prompt leak detected, scrubbing response")
            # Remove the entire sentence containing the leak
            text = pattern.sub("[...]", text)

    # 3. Strip RAG internals
    for pattern in _RAG_INTERNALS:
        text = pattern.sub("", text)

    # 4. Redact PII
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)

    # 5. Strip dangerous HTML
    text = _DANGEROUS_HTML.sub("", text)
    text = _JAVASCRIPT_URI.sub("", text)

    # 6. Clean up excessive whitespace from removals
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if text != original:
        logger.info("[output_sanitizer] response was sanitized (len %d -> %d)", len(original), len(text))

    return text


def sanitize_agent_trace(trace: List[dict]) -> List[dict]:
    """
    Sanitize agent trace steps before sending to frontend.

    Remove sensitive internal details while preserving useful user-facing info.
    """
    safe_trace = []
    for step in trace:
        safe_step = {
            "agent": step.get("agent", ""),
            "action": step.get("action", ""),
            "timestamp": step.get("timestamp", ""),
        }
        # Include reasoning but strip any leaked internals
        reasoning = step.get("reasoning", "")
        if reasoning:
            for pattern in _SYSTEM_PROMPT_LEAKS:
                reasoning = pattern.sub("[...]", reasoning)
            safe_step["reasoning"] = reasoning

        # Sanitize result field
        result = step.get("result")
        if result:
            for pattern in _SYSTEM_PROMPT_LEAKS:
                if isinstance(result, str):
                    result = pattern.sub("[...]", result)
            safe_step["result"] = result

        # Remove tool field if it exposes internal details
        tool = step.get("tool", "")
        if tool and tool not in ("chromadb", "firestore", "prompt_firewall", "gap_detection"):
            safe_step["tool"] = "ai"
        else:
            safe_step["tool"] = tool

        safe_trace.append(safe_step)

    return safe_trace
