"""
Prompt Injection Defense Layer for Touri AI system.

Detects and neutralizes:
- Fake system instruction injections
- Roleplay/jailbreak attempts
- XML/JSON/tool injection patterns
- UI_TRIGGER spoofing
- Instruction override attempts
- Chain-of-thought extraction attempts

Returns a sanitized prompt and an injection risk score (0.0 - 1.0).
Score >= 0.7 = block the request. Score >= 0.4 = flag for review.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger("touri.prompt_firewall")


@dataclass
class FirewallResult:
    """Result of prompt firewall analysis."""

    sanitized_text: str
    risk_score: float
    flags: List[str]
    blocked: bool


# ── Detection patterns ────────────────────────────────────────────────────────

# System instruction injection patterns
_SYSTEM_INJECTION_PATTERNS = [
    re.compile(r"(?:you are now|new instructions?|ignore (?:all )?previous|forget (?:all )?(?:previous|your)|disregard (?:all )?(?:previous|your|above))", re.IGNORECASE),
    re.compile(r"(?:system ?(?:prompt|message|instruction)|<\|?system\|?>|<<SYS>>|\[INST\]|\[/INST\])", re.IGNORECASE),
    re.compile(r"(?:act as|pretend (?:to be|you are)|you(?:'re| are) (?:now|actually)|from now on (?:you|act))", re.IGNORECASE),
    re.compile(r"(?:override|overwrite|replace|rewrite|update)\s+(?:your|the|system)\s+(?:instructions?|prompt|rules?|guidelines?)", re.IGNORECASE),
]

# Prompt extraction attempts
_EXTRACTION_PATTERNS = [
    re.compile(r"(?:reveal|show|display|print|output|repeat|tell me)\s+(?:your|the|system)\s+(?:prompt|instructions?|rules?|guidelines?|system message)", re.IGNORECASE),
    re.compile(r"(?:what (?:are|is) your|show me your|repeat your)\s+(?:instructions?|system prompt|rules|initial prompt|hidden prompt)", re.IGNORECASE),
    re.compile(r"(?:chain.of.thought|internal (?:reasoning|thoughts?|monologue)|hidden (?:reasoning|thoughts?))", re.IGNORECASE),
    re.compile(r"(?:dump|export|leak|expose)\s+(?:your|the|system|internal)", re.IGNORECASE),
]

# Roleplay jailbreak patterns
_JAILBREAK_PATTERNS = [
    re.compile(r"(?:DAN|do anything now|jailbreak|unfiltered|no restrictions|no rules|no guidelines)", re.IGNORECASE),
    re.compile(r"(?:developer mode|god mode|admin mode|maintenance mode|debug mode|unrestricted mode)", re.IGNORECASE),
    re.compile(r"(?:hypothetically|in a fictional|for (?:educational|research|academic) purposes?|imagine (?:you|a world))", re.IGNORECASE),
]

# XML/JSON/tool injection
_TOOL_INJECTION_PATTERNS = [
    re.compile(r"<(?:tool_call|function_call|tool_use|api_call|execute)(?:\s|>)", re.IGNORECASE),
    re.compile(r"\{\"(?:tool|function|action|command)\":", re.IGNORECASE),
    re.compile(r"<\|(?:im_start|im_end|endoftext|assistant|system)\|>", re.IGNORECASE),
]

# UI_TRIGGER spoofing
_UI_TRIGGER_PATTERNS = [
    re.compile(r"---\s*UI_TRIGGER\s*---", re.IGNORECASE),
    re.compile(r"UI_TRIGGER", re.IGNORECASE),
    re.compile(r"(?:trigger|emit|send|fire)\s+(?:a\s+)?(?:UI|interface|frontend)\s+(?:event|trigger|action)", re.IGNORECASE),
]

# Architecture disclosure attempts
_ARCHITECTURE_PATTERNS = [
    re.compile(r"(?:what (?:model|LLM|AI)|which (?:model|language model)|running on|powered by|architecture|backend|LangGraph|ChromaDB)", re.IGNORECASE),
    re.compile(r"(?:how (?:many|are) (?:your )?agents?|router agent|travel planner agent|budget specialist|local concierge)", re.IGNORECASE),
]


def _score_patterns(text: str, patterns: List[re.Pattern], weight: float) -> Tuple[float, List[str]]:
    """Score text against a list of patterns. Returns (score_contribution, flags)."""
    flags = []
    score = 0.0
    for pat in patterns:
        if pat.search(text):
            score += weight
            flags.append(f"matched:{pat.pattern[:50]}")
    return min(score, weight * 2), flags  # Cap contribution


def analyze_prompt(text: str) -> FirewallResult:
    """
    Analyze user input for prompt injection attempts.

    Returns a FirewallResult with sanitized text, risk score, and flags.
    """
    if not text or not text.strip():
        return FirewallResult(sanitized_text=text, risk_score=0.0, flags=[], blocked=False)

    total_score = 0.0
    all_flags: List[str] = []

    # Check each category
    score, flags = _score_patterns(text, _SYSTEM_INJECTION_PATTERNS, 0.35)
    total_score += score
    all_flags.extend(flags)

    score, flags = _score_patterns(text, _EXTRACTION_PATTERNS, 0.40)
    total_score += score
    all_flags.extend(flags)

    score, flags = _score_patterns(text, _JAILBREAK_PATTERNS, 0.30)
    total_score += score
    all_flags.extend(flags)

    score, flags = _score_patterns(text, _TOOL_INJECTION_PATTERNS, 0.45)
    total_score += score
    all_flags.extend(flags)

    score, flags = _score_patterns(text, _UI_TRIGGER_PATTERNS, 0.50)
    total_score += score
    all_flags.extend(flags)

    score, flags = _score_patterns(text, _ARCHITECTURE_PATTERNS, 0.15)
    total_score += score
    all_flags.extend(flags)

    # Cap at 1.0
    total_score = min(total_score, 1.0)

    # Sanitize: strip dangerous control sequences
    sanitized = _sanitize_prompt(text)

    blocked = total_score >= 0.7

    if total_score >= 0.4:
        logger.warning(
            "[prompt_firewall] elevated risk=%.2f flags=%d text_preview='%s'",
            total_score,
            len(all_flags),
            text[:100],
        )

    if blocked:
        logger.error(
            "[prompt_firewall] BLOCKED injection attempt score=%.2f flags=%s",
            total_score,
            all_flags[:5],
        )

    return FirewallResult(
        sanitized_text=sanitized,
        risk_score=total_score,
        flags=all_flags,
        blocked=blocked,
    )


def _sanitize_prompt(text: str) -> str:
    """Strip dangerous control patterns from user input while preserving intent."""
    sanitized = text

    # Remove fake system/instruction blocks
    sanitized = re.sub(r"<\|?system\|?>.*?<\|?/system\|?>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r"<<SYS>>.*?<</SYS>>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r"\[INST\].*?\[/INST\]", "", sanitized, flags=re.DOTALL | re.IGNORECASE)

    # Remove UI_TRIGGER blocks from user input
    sanitized = re.sub(r"---\s*UI_TRIGGER\s*---.*?(?=---|$)", "", sanitized, flags=re.DOTALL | re.IGNORECASE)

    # Remove fake tool call XML
    sanitized = re.sub(r"<(?:tool_call|function_call|tool_use|execute)[^>]*>.*?</(?:tool_call|function_call|tool_use|execute)>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)

    # Remove special tokens
    sanitized = re.sub(r"<\|(?:im_start|im_end|endoftext|assistant|system|user)\|>", "", sanitized)

    return sanitized.strip()
