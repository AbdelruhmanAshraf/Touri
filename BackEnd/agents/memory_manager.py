"""
Memory Manager — LangGraph-aware memory orchestration.

Responsibilities
----------------
1. **Pre-response**: Load user memory (preferences, summary, recent history)
   and inject it into the agent state before routing.
2. **Post-response**: Extract preferences from the exchange, persist the
   message pair, and update the conversation summary when threshold is hit.
3. **Summarisation**: Compress old messages into a rolling summary to prevent
   token explosion while retaining key context.

This module is called by the graph (as a node or utility) — NOT as a
standalone agent. It never generates user-facing text.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.llm import FAST_MODEL, get_llm, safe_extract_text, t
from agents.state import AgentState, make_step
from services.conversation_state import (
    ConversationState,
    determine_next_state,
    load_conversation_state,
    save_conversation_state,
)
from services.memory_service import (
    ConversationSummary,
    MemoryContext,
    extract_preferences_from_message,
    format_memory_for_prompt,
    get_all_session_messages,
    get_conversation_summary,
    load_memory_context,
    save_conversation_summary,
    save_generated_plan,
    save_message,
    update_travel_preferences,
    cleanup_stale_sessions,
)

logger = logging.getLogger(__name__)

# Max messages before triggering summarisation
_SUMMARY_TRIGGER = 30
# Cleanup counter — run stale session cleanup every ~50 exchanges
_cleanup_counter = 0
_CLEANUP_INTERVAL = 50


# ── Pre-response: Load memory into state ────────────────────────────────────
async def load_memory_into_state(state: AgentState) -> AgentState:
    """
    LangGraph node (or utility): loads persistent memory and injects it
    into the state so downstream agents have full conversational context.
    """
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    language = state.get("language", "en")

    if not user_id:
        return state

    # Build persona summary from state if available
    persona = state.get("user_persona")
    persona_summary = ""
    if persona:
        parts = []
        name = " ".join(filter(None, [persona.first_name, persona.last_name]))
        if name:
            parts.append(f"name={name}")
        parts.append(f"tourism_type={persona.tourism_type.value}")
        parts.append(f"party_size={persona.party_size}")
        parts.append(f"budget={persona.budget_bracket.value}")
        if persona.preferred_destination:
            parts.append(f"destination={persona.preferred_destination}")
        if persona.extras:
            for k, v in persona.extras.items():
                if v:
                    parts.append(f"{k}={v}")
        persona_summary = ", ".join(parts)

    try:
        ctx = await load_memory_context(user_id, session_id, persona_summary)
        # Inject memory context as a formatted string for prompt use
        state["memory_context"] = format_memory_for_prompt(ctx, language)
        state["travel_preferences"] = ctx.travel_preferences.model_dump() if ctx.travel_preferences else {}

        # Merge stored chat history with any client-provided history
        if ctx.recent_messages and not state.get("chat_history"):
            state["chat_history"] = [
                {"role": m["role"], "content": m["content"]}
                for m in ctx.recent_messages
            ]

        # Load conversation state machine
        try:
            conv_state = await load_conversation_state(user_id, session_id)
            conv_state.increment_turn()
            state["conversation_state"] = conv_state.model_dump()
            state["requirements_status"] = conv_state.requirements_status().model_dump()
        except Exception as cs_exc:
            logger.warning("[memory_manager] load conversation state failed: %s", cs_exc)

        state["agent_trace"].append(
            make_step(
                agent="Memory Manager",
                action=t(language, "Load memory context", "تحميل سياق الذاكرة"),
                tool="firestore",
                reasoning=t(
                    language,
                    f"Loaded {len(ctx.recent_messages)} recent messages, "
                    f"{len(ctx.key_facts)} key facts, "
                    f"{'with' if ctx.conversation_summary else 'no'} conversation summary.",
                    f"تم تحميل {len(ctx.recent_messages)} رسالة حديثة، "
                    f"{len(ctx.key_facts)} حقيقة مهمة، "
                    f"{'مع' if ctx.conversation_summary else 'بدون'} ملخص محادثة.",
                ),
                result=f"msgs={len(ctx.recent_messages)}, facts={len(ctx.key_facts)}",
            )
        )
    except Exception as exc:
        logger.warning("[memory_manager] load_memory failed: %s", exc)
        state["memory_context"] = ""
        state["travel_preferences"] = {}

    return state


# ── Post-response: Persist message pair + extract preferences ───────────────
async def persist_exchange(
    *,
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    agent: Optional[str] = None,
    intent: Optional[str] = None,
    itinerary: Optional[Dict[str, Any]] = None,
    conversation_state_dict: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Called after each exchange. Persists both messages and extracts
    any travel preferences from the conversation.
    """
    if not user_id:
        return

    # 1. Save user message
    await save_message(
        user_id=user_id,
        session_id=session_id,
        role="user",
        content=user_message,
        intent=intent,
    )

    # 2. Save assistant response
    await save_message(
        user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=assistant_response,
        agent=agent,
        intent=intent,
    )

    # 3. Extract and save preferences
    try:
        pref_updates = extract_preferences_from_message(user_message, assistant_response)
        if pref_updates:
            await update_travel_preferences(user_id, pref_updates)
            logger.debug("[memory_manager] extracted prefs: %s", list(pref_updates.keys()))
    except Exception as exc:
        logger.warning("[memory_manager] preference extraction failed: %s", exc)

    # 4. Save plan reference if itinerary was generated
    if itinerary:
        try:
            await save_generated_plan(user_id, itinerary)
        except Exception as exc:
            logger.warning("[memory_manager] save_generated_plan failed: %s", exc)

    # 5. Auto-summarise if the session is getting long
    try:
        await maybe_summarise(user_id, session_id)
    except Exception as exc:
        logger.warning("[memory_manager] auto-summarise failed: %s", exc)

    # 5b. Update conversation state if provided
    if conversation_state_dict:
        try:
            conv = ConversationState(**conversation_state_dict)
            # Determine state transition based on intent
            missing = conv.missing_requirements
            next_state = determine_next_state(conv, intent or "general", missing)
            if next_state and conv.can_transition(next_state):
                conv.transition(next_state)
            if agent:
                conv.active_agent = agent
            await save_conversation_state(user_id, conv)
        except Exception as exc:
            logger.warning("[memory_manager] conversation state update failed: %s", exc)

    # 6. Periodic stale session cleanup
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter >= _CLEANUP_INTERVAL:
        _cleanup_counter = 0
        try:
            await cleanup_stale_sessions(user_id)
        except Exception as exc:
            logger.warning("[memory_manager] cleanup_stale_sessions failed: %s", exc)


# ── Summarisation ───────────────────────────────────────────────────────────
async def maybe_summarise(user_id: str, session_id: str) -> None:
    """
    Check if the conversation is long enough to warrant summarisation.
    If so, generate a rolling summary and clear old messages from context.
    """
    from services.memory_service import get_all_session_messages

    try:
        messages = await get_all_session_messages(user_id, session_id)
        if len(messages) < _SUMMARY_TRIGGER:
            return

        existing = await get_conversation_summary(user_id)
        existing_text = existing.summary_text if existing else ""
        existing_count = existing.message_count if existing else 0

        # Build messages text for summarisation
        msg_text_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")[:200]
            msg_text_parts.append(f"[{role}]: {content}")
        conversation_block = "\n".join(msg_text_parts[-_SUMMARY_TRIGGER:])

        # Use LLM to summarise
        llm = get_llm(model=FAST_MODEL, temperature=0.1, streaming=False)
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = (
            f"Summarise this travel conversation into a concise paragraph (max 300 words). "
            f"Focus on: destinations discussed, preferences expressed, decisions made, "
            f"plans generated, and any important user constraints.\n\n"
            f"{'Previous summary: ' + existing_text + chr(10) + chr(10) if existing_text else ''}"
            f"New messages:\n{conversation_block}"
        )

        resp = await llm.ainvoke([
            SystemMessage(content="You are a conversation summariser. Output only the summary, no commentary."),
            HumanMessage(content=prompt),
        ])
        summary_text = safe_extract_text(resp.content)

        # Extract key topics
        key_topics = []
        topic_keywords = [
            "cairo", "alexandria", "luxor", "aswan", "hurghada", "budget",
            "hotel", "restaurant", "itinerary", "plan", "medical",
        ]
        for kw in topic_keywords:
            if kw in summary_text.lower():
                key_topics.append(kw)

        new_summary = ConversationSummary(
            summary_text=summary_text[:2000],
            message_count=existing_count + len(messages),
            key_topics=key_topics,
            inferred_preferences={},
        )
        await save_conversation_summary(user_id, new_summary)
        logger.info("[memory_manager] summarised %d messages for user=%s", len(messages), user_id)

    except Exception as exc:
        logger.warning("[memory_manager] summarisation failed: %s", exc)


__all__ = [
    "load_memory_into_state",
    "persist_exchange",
    "maybe_summarise",
]
