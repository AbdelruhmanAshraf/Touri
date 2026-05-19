"""
Persistent conversational memory service — Firestore-backed.

Firestore structure
-------------------
users/{uid}/memory/profile            → travel preferences summary doc
users/{uid}/memory/conversation_summary → rolling conversation summary
users/{uid}/chats/{sid}       → session metadata
users/{uid}/chats/{sid}/messages/{auto} → individual messages
users/{uid}/travel_preferences/prefs  → structured preference fields

Features
--------
* Per-user, per-session message persistence
* Travel preference extraction + accumulation
* Conversation summarisation for long chats (token control)
* Semantic memory retrieval via keyword matching
* Bilingual Arabic/English support
* Automatic cleanup + last_active timestamps
* Session chunking (max 50 messages per summary cycle)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from memory.firebase_client import get_db, is_ready as firebase_ready

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
_MAX_HISTORY_MESSAGES = 20        # Max recent messages to load as context
_MAX_CROSS_SESSION_MESSAGES = 10  # Max messages to load from OTHER sessions
_SUMMARY_THRESHOLD = 30           # Summarise when session exceeds this many msgs
_MAX_SUMMARY_CHARS = 2000         # Max chars for conversation summary
_SESSION_STALE_DAYS = 30          # Sessions older than this are candidates for cleanup
_MAX_STORED_PLANS = 5             # Max generated plans to keep per user
_PREFERENCE_FIELDS = [
    "favorite_cities", "disliked_activities", "dietary_restrictions",
    "allergies", "preferred_language", "spending_behavior",
    "preferred_trip_pacing", "rejected_recommendations",
    "hotel_preferences", "transportation_preferences",
    "travel_style", "family_size", "budget_preferences",
]


# ── Models ───────────────────────────────────────────────────────────────────
class TravelPreferences(BaseModel):
    """Structured travel preferences persisted per user."""
    favorite_cities: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    preferred_language: str = "en"
    spending_behavior: Optional[str] = None       # "frugal" | "moderate" | "generous"
    preferred_trip_pacing: Optional[str] = None    # "relaxed" | "moderate" | "packed"
    rejected_recommendations: List[str] = Field(default_factory=list)
    hotel_preferences: Optional[str] = None        # "resort" | "apartment" | "hotel" | "boutique"
    transportation_preferences: Optional[str] = None  # "walking" | "uber" | "rental" | "public"
    travel_style: Optional[str] = None             # "luxury" | "adventure" | "relaxation" | "historical"
    family_size: Optional[int] = None
    budget_preferences: Optional[str] = None       # "economy" | "mid_range" | "luxury"
    trip_duration: Optional[int] = None            # e.g. 5 days
    selected_cities: List[str] = Field(default_factory=list)
    generated_plans: List[Dict[str, Any]] = Field(default_factory=list, max_length=5)
    updated_at: Optional[str] = None


class ChatMessageDoc(BaseModel):
    """Single chat message document for Firestore."""
    role: str                    # "user" | "assistant"
    content: str
    agent: Optional[str] = None
    intent: Optional[str] = None
    timestamp: str
    session_id: str
    # Truncated summary for long messages (token control)
    content_summary: Optional[str] = None


class ConversationSummary(BaseModel):
    """Rolling summary of a conversation for context injection."""
    summary_text: str = ""
    message_count: int = 0
    key_topics: List[str] = Field(default_factory=list)
    inferred_preferences: Dict[str, Any] = Field(default_factory=dict)
    last_updated: Optional[str] = None


class MemoryContext(BaseModel):
    """Assembled memory context ready for LLM prompt injection."""
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    cross_session_messages: List[Dict[str, str]] = Field(default_factory=list)
    conversation_summary: str = ""
    travel_preferences: Optional[TravelPreferences] = None
    onboarding_persona_summary: str = ""
    previous_plans_summary: str = ""
    key_facts: List[str] = Field(default_factory=list)


# ── In-memory fallback ───────────────────────────────────────────────────────
_mem_store: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(content: str) -> str:
    """Short hash to detect duplicate messages."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]


# ── Message persistence ─────────────────────────────────────────────────────
async def save_message(
    *,
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    agent: Optional[str] = None,
    intent: Optional[str] = None,
) -> bool:
    """Persist a single chat message to Firestore."""
    ts = _now_iso()
    # Truncate very long messages for storage efficiency
    content_summary = None
    if len(content) > 2000:
        content_summary = content[:500] + "..."

    doc_data = {
        "role": role,
        "content": content[:10000],  # Hard cap at 10k chars
        "content_summary": content_summary,
        "agent": agent,
        "intent": intent,
        "timestamp": ts,
        "session_id": session_id,
        "content_hash": _content_hash(content),
    }

    if not firebase_ready():
        # Fallback to in-memory
        key = f"{user_id}:{session_id}"
        _mem_store.setdefault(key, {"messages": [], "meta": {}})
        _mem_store[key]["messages"].append(doc_data)
        return True

    try:
        db = get_db()
        # Save message
        msg_ref = (
            db.collection("users").document(user_id)
            .collection("chats").document(session_id)
            .collection("messages")
        )

        # Dedup: check if a message with the same content_hash was recently added
        content_hash = doc_data.get("content_hash", "")
        if content_hash:
            recent = list(
                msg_ref.where("content_hash", "==", content_hash)
                .order_by("timestamp")
                .limit_to_last(1)
                .get()
            )
            if recent:
                return True  # Already stored

        msg_ref.add(doc_data)

        # Update session metadata — use increment instead of counting
        from google.cloud.firestore_v1 import Increment
        session_ref = (
            db.collection("users").document(user_id)
            .collection("chats").document(session_id)
        )
        session_update = {
            "last_active": ts,
            "session_id": session_id,
            "message_count": Increment(1),
            "last_message_preview": content[:100],
        }
        if not session_ref.get().exists:
            session_update["created_at"] = ts
        session_ref.set(session_update, merge=True)

        return True
    except Exception as exc:
        logger.warning("[memory_service] save_message failed: %s", exc)
        key = f"{user_id}:{session_id}"
        _mem_store.setdefault(key, {"messages": [], "meta": {}})
        _mem_store[key]["messages"].append(doc_data)
        return True


async def get_recent_messages(
    user_id: str,
    session_id: str,
    limit: int = _MAX_HISTORY_MESSAGES,
) -> List[Dict[str, str]]:
    """Retrieve the last N messages from a session, newest last."""
    if not firebase_ready():
        key = f"{user_id}:{session_id}"
        msgs = _mem_store.get(key, {}).get("messages", [])
        return [{"role": m["role"], "content": m["content"]} for m in msgs[-limit:]]

    try:
        db = get_db()
        docs = (
            db.collection("users").document(user_id)
            .collection("chats").document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .limit_to_last(limit)
            .get()
        )
        return [
            {"role": d.to_dict()["role"], "content": d.to_dict()["content"]}
            for d in docs
        ]
    except Exception as exc:
        logger.warning("[memory_service] get_recent_messages failed: %s", exc)
        key = f"{user_id}:{session_id}"
        msgs = _mem_store.get(key, {}).get("messages", [])
        return [{"role": m["role"], "content": m["content"]} for m in msgs[-limit:]]


async def get_all_session_messages(user_id: str, session_id: str) -> List[Dict[str, Any]]:
    """Get all messages in a session (for summarisation)."""
    if not firebase_ready():
        key = f"{user_id}:{session_id}"
        return _mem_store.get(key, {}).get("messages", [])

    try:
        db = get_db()
        docs = (
            db.collection("users").document(user_id)
            .collection("chats").document(session_id)
            .collection("messages")
            .order_by("timestamp")
            .get()
        )
        return [d.to_dict() for d in docs]
    except Exception as exc:
        logger.warning("[memory_service] get_all_session_messages failed: %s", exc)
        return []


# ── Conversation summary ────────────────────────────────────────────────────
async def get_conversation_summary(user_id: str) -> Optional[ConversationSummary]:
    """Load the rolling conversation summary for a user."""
    if not firebase_ready():
        return None
    try:
        db = get_db()
        doc = (
            db.collection("users").document(user_id)
            .collection("memory").document("conversation_summary")
            .get()
        )
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return ConversationSummary(**data)
    except Exception as exc:
        logger.warning("[memory_service] get_conversation_summary failed: %s", exc)
        return None


async def save_conversation_summary(
    user_id: str, summary: ConversationSummary
) -> bool:
    """Persist the conversation summary."""
    summary.last_updated = _now_iso()
    if not firebase_ready():
        return False
    try:
        db = get_db()
        (
            db.collection("users").document(user_id)
            .collection("memory").document("conversation_summary")
            .set(summary.model_dump(), merge=True)
        )
        return True
    except Exception as exc:
        logger.warning("[memory_service] save_conversation_summary failed: %s", exc)
        return False


# ── Travel preferences ──────────────────────────────────────────────────────
async def get_travel_preferences(user_id: str) -> Optional[TravelPreferences]:
    """Load structured travel preferences from Firestore."""
    if not firebase_ready():
        return None
    try:
        db = get_db()
        doc = (
            db.collection("users").document(user_id)
            .collection("travel_preferences").document("prefs")
            .get()
        )
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return TravelPreferences(**{k: v for k, v in data.items() if k in TravelPreferences.model_fields})
    except Exception as exc:
        logger.warning("[memory_service] get_travel_preferences failed: %s", exc)
        return None


async def update_travel_preferences(
    user_id: str, updates: Dict[str, Any]
) -> Optional[TravelPreferences]:
    """Merge new preference data into existing preferences."""
    current = await get_travel_preferences(user_id) or TravelPreferences()

    # Smart merge: append to lists, overwrite scalars
    for key, value in updates.items():
        if key not in TravelPreferences.model_fields:
            continue
        current_val = getattr(current, key, None)
        if isinstance(current_val, list) and isinstance(value, list):
            # Deduplicate when appending
            merged = list(current_val)
            for item in value:
                if item not in merged:
                    merged.append(item)
            setattr(current, key, merged)
        elif isinstance(current_val, list) and isinstance(value, str):
            if value not in current_val:
                current_val.append(value)
        else:
            setattr(current, key, value)

    current.updated_at = _now_iso()

    if not firebase_ready():
        return current

    try:
        db = get_db()
        (
            db.collection("users").document(user_id)
            .collection("travel_preferences").document("prefs")
            .set(current.model_dump(), merge=True)
        )
        return current
    except Exception as exc:
        logger.warning("[memory_service] update_travel_preferences failed: %s", exc)
        return current


# ── Full memory context assembly ─────────────────────────────────────────────
async def load_memory_context(
    user_id: str,
    session_id: str,
    persona_summary: str = "",
) -> MemoryContext:
    """
    Assemble the full memory context for LLM prompt injection.

    Loads recent messages, conversation summary, travel preferences,
    and onboarding persona — all token-efficient with truncation.
    """
    recent = await get_recent_messages(user_id, session_id, limit=_MAX_HISTORY_MESSAGES)
    conv_summary = await get_conversation_summary(user_id)
    prefs = await get_travel_preferences(user_id)

    # Load cross-session context if current session has few messages
    cross_session: List[Dict[str, str]] = []
    if len(recent) < 4:
        cross_session = await get_cross_session_messages(user_id, session_id)

    # Build key facts from preferences for quick LLM reference
    key_facts: List[str] = []
    if prefs:
        if prefs.favorite_cities:
            key_facts.append(f"Favorite cities: {', '.join(prefs.favorite_cities[:5])}")
        if prefs.disliked_activities:
            key_facts.append(f"Dislikes: {', '.join(prefs.disliked_activities[:5])}")
        if prefs.dietary_restrictions:
            key_facts.append(f"Dietary: {', '.join(prefs.dietary_restrictions)}")
        if prefs.allergies:
            key_facts.append(f"Allergies: {', '.join(prefs.allergies)}")
        if prefs.hotel_preferences:
            key_facts.append(f"Hotel preference: {prefs.hotel_preferences}")
        if prefs.transportation_preferences:
            key_facts.append(f"Transport preference: {prefs.transportation_preferences}")
        if prefs.travel_style:
            key_facts.append(f"Travel style: {prefs.travel_style}")
        if prefs.spending_behavior:
            key_facts.append(f"Spending: {prefs.spending_behavior}")
        if prefs.rejected_recommendations:
            key_facts.append(f"Previously rejected: {', '.join(prefs.rejected_recommendations[:5])}")
        if prefs.selected_cities:
            key_facts.append(f"Selected cities: {', '.join(prefs.selected_cities[:5])}")

    # Build plan summary from stored plans
    plans_summary = ""
    if prefs and prefs.generated_plans:
        plan_strs = []
        for p in prefs.generated_plans[-3:]:
            city = p.get("city", "")
            dur = p.get("duration", "")
            plan_strs.append(f"{city} ({dur} days)" if dur else city)
        if plan_strs:
            plans_summary = f"Previous plans: {', '.join(plan_strs)}"

    return MemoryContext(
        recent_messages=recent,
        conversation_summary=(conv_summary.summary_text if conv_summary else ""),
        travel_preferences=prefs,
        onboarding_persona_summary=persona_summary,
        previous_plans_summary=plans_summary,
        key_facts=key_facts,
        cross_session_messages=cross_session,
    )


def format_memory_for_prompt(ctx: MemoryContext, language: str = "en") -> str:
    """
    Format memory context into a concise string for LLM prompt injection.
    Includes a strong "do not re-ask" enforcement directive.
    Keeps total under ~1500 tokens for efficiency.
    """
    sections: List[str] = []

    # 0. CRITICAL: Do-not-re-ask enforcement directive
    if language == "ar":
        sections.append(
            "⚠️ تعليمات صارمة: لا تسأل المستخدم أبدًا عن معلومات موجودة أدناه. "
            "هذه المعلومات محفوظة في الذاكرة. استخدمها مباشرة. "
            "اسأل فقط عن المعلومات الناقصة التي لم تُذكر."
        )
    else:
        sections.append(
            "STRICT RULE: NEVER re-ask the user for any information already listed below. "
            "This data is persisted in memory. Use it directly in your response. "
            "Only ask about fields that are genuinely missing and not mentioned anywhere below."
        )

    # 1. Key facts (most important, always included)
    if ctx.key_facts:
        header = "حقائق المستخدم المهمة:" if language == "ar" else "Key user facts:"
        sections.append(f"{header}\n" + "\n".join(f"- {f}" for f in ctx.key_facts))

    # 2. Conversation summary (if exists)
    if ctx.conversation_summary:
        header = "ملخص المحادثة السابقة:" if language == "ar" else "Previous conversation summary:"
        summary = ctx.conversation_summary[:_MAX_SUMMARY_CHARS]
        sections.append(f"{header}\n{summary}")

    # 3. Previous plans
    if ctx.previous_plans_summary:
        sections.append(ctx.previous_plans_summary)

    # 4. Onboarding persona
    if ctx.onboarding_persona_summary:
        header = "ملف المستخدم:" if language == "ar" else "User profile:"
        sections.append(f"{header} {ctx.onboarding_persona_summary}")

    # 5. Travel preferences (structured data for direct use)
    if ctx.travel_preferences:
        prefs = ctx.travel_preferences
        pref_parts: List[str] = []
        if prefs.selected_cities:
            pref_parts.append(f"destination={', '.join(prefs.selected_cities)}")
        if prefs.trip_duration:
            pref_parts.append(f"trip_duration={prefs.trip_duration} days")
        if prefs.budget_preferences:
            pref_parts.append(f"budget={prefs.budget_preferences}")
        if prefs.family_size:
            pref_parts.append(f"party_size={prefs.family_size}")
        if prefs.dietary_restrictions:
            pref_parts.append(f"dietary={', '.join(prefs.dietary_restrictions)}")
        if prefs.allergies:
            pref_parts.append(f"allergies={', '.join(prefs.allergies)}")
        if prefs.hotel_preferences:
            pref_parts.append(f"hotel_style={prefs.hotel_preferences}")
        if prefs.preferred_trip_pacing:
            pref_parts.append(f"pace={prefs.preferred_trip_pacing}")
        if pref_parts:
            header = "تفضيلات محفوظة (لا تسأل عنها):" if language == "ar" else "Stored preferences (DO NOT ask again):"
            sections.append(f"{header}\n" + "\n".join(f"- {p}" for p in pref_parts))

    # 6. Recent messages (last 6 for conciseness)
    if ctx.recent_messages:
        header = "الرسائل الأخيرة:" if language == "ar" else "Recent messages:"
        msg_lines = []
        for m in ctx.recent_messages[-6:]:
            role_label = m["role"].capitalize()
            content = m["content"][:300]
            if len(m["content"]) > 300:
                content += "..."
            msg_lines.append(f"[{role_label}]: {content}")
        sections.append(f"{header}\n" + "\n".join(msg_lines))

    # 7. Cross-session context (for continuity across sessions)
    if ctx.cross_session_messages:
        header = "رسائل من محادثات سابقة:" if language == "ar" else "From previous conversations:"
        msg_lines = []
        for m in ctx.cross_session_messages[-4:]:
            role_label = m["role"].capitalize()
            content = m["content"][:200]
            msg_lines.append(f"[{role_label}]: {content}")
        sections.append(f"{header}\n" + "\n".join(msg_lines))

    return "\n\n".join(sections)


# ── Preference extraction from messages ──────────────────────────────────────
def extract_preferences_from_message(
    message: str, response: str, current_prefs: Optional[TravelPreferences] = None
) -> Dict[str, Any]:
    """
    Extract travel preferences from a user message + AI response pair.
    Returns a dict of fields to update. Lightweight heuristic extraction
    (no LLM call) to avoid unnecessary token usage.
    """
    updates: Dict[str, Any] = {}
    msg_lower = message.lower()

    # City mentions
    city_map = {
        "cairo": "Cairo", "القاهرة": "Cairo",
        "alexandria": "Alexandria", "الإسكندرية": "Alexandria", "الاسكندرية": "Alexandria",
        "luxor": "Luxor", "الأقصر": "Luxor", "الاقصر": "Luxor",
        "aswan": "Aswan", "أسوان": "Aswan", "اسوان": "Aswan",
        "hurghada": "Hurghada", "الغردقة": "Hurghada",
        "sharm": "Sharm El Sheikh", "شرم": "Sharm El Sheikh",
        "dahab": "Dahab", "دهب": "Dahab",
        "siwa": "Siwa", "سيوة": "Siwa",
    }
    found_cities = []
    for kw, city in city_map.items():
        if kw in msg_lower:
            found_cities.append(city)
    if found_cities:
        updates["selected_cities"] = found_cities

    # Budget mentions
    budget_kw = {
        "economy": "economy", "اقتصادي": "economy", "cheap": "economy", "رخيص": "economy",
        "mid-range": "mid_range", "moderate": "mid_range", "متوسط": "mid_range",
        "luxury": "luxury", "فاخر": "luxury", "premium": "luxury",
    }
    for kw, val in budget_kw.items():
        if kw in msg_lower:
            updates["budget_preferences"] = val
            break

    # Hotel style
    hotel_kw = {
        "resort": "resort", "منتجع": "resort",
        "apartment": "apartment", "شقة": "apartment",
        "boutique": "boutique", "بوتيك": "boutique",
        "hostel": "hostel", "نزل": "hostel",
    }
    for kw, val in hotel_kw.items():
        if kw in msg_lower:
            updates["hotel_preferences"] = val
            break

    # Travel style
    style_kw = {
        "adventure": "adventure", "مغامرة": "adventure",
        "relaxation": "relaxation", "استرخاء": "relaxation", "relax": "relaxation",
        "historical": "historical", "تاريخي": "historical", "history": "historical",
        "cultural": "cultural", "ثقافي": "cultural",
    }
    for kw, val in style_kw.items():
        if kw in msg_lower:
            updates["travel_style"] = val
            break

    # Duration mentions
    import re
    duration_m = re.search(r"(\d+)\s*(?:day|days|يوم|أيام|ايام|night|nights|ليلة|ليالي|week|weeks|أسبوع|اسبوع)", message, re.IGNORECASE)
    if duration_m:
        val = int(duration_m.group(1))
        if re.search(r"\b(week|أسبوع|اسبوع)\b", message, re.IGNORECASE):
            val *= 7
        updates["trip_duration"] = val

    # Transport
    transport_kw = {
        "uber": "uber", "أوبر": "uber",
        "rental car": "rental", "سيارة": "rental",
        "public transport": "public", "مواصلات": "public",
        "walking": "walking", "مشي": "walking",
    }
    for kw, val in transport_kw.items():
        if kw in msg_lower:
            updates["transportation_preferences"] = val
            break

    # Negative signals (disliked activities)
    dislike_patterns = [
        "don't like", "hate", "avoid", "no ", "not interested in",
        "لا أحب", "أكره", "تجنب", "بدون",
    ]
    for pat in dislike_patterns:
        if pat in msg_lower:
            # Simple extraction: grab the words after the dislike pattern
            idx = msg_lower.index(pat)
            snippet = message[idx + len(pat):idx + len(pat) + 50].strip()
            if snippet:
                updates.setdefault("disliked_activities", [])
                updates["disliked_activities"].append(snippet.split(".")[0].strip())
            break

    return updates


# ── Save generated plan reference ────────────────────────────────────────────
async def save_generated_plan(
    user_id: str, plan_summary: Dict[str, Any]
) -> None:
    """Append a plan summary (city, duration) to user's plan history."""
    prefs = await get_travel_preferences(user_id) or TravelPreferences()
    plans = list(prefs.generated_plans[-(_MAX_STORED_PLANS - 1):])
    plans.append({
        "city": plan_summary.get("city", ""),
        "duration": plan_summary.get("duration", 0),
        "timestamp": _now_iso(),
    })
    await update_travel_preferences(user_id, {"generated_plans": plans})


# ── Cross-session message retrieval ──────────────────────────────────────────
async def get_cross_session_messages(
    user_id: str,
    current_session_id: str,
    limit: int = _MAX_CROSS_SESSION_MESSAGES,
) -> List[Dict[str, str]]:
    """Retrieve recent messages from OTHER sessions for cross-session context."""
    if not firebase_ready():
        return []
    try:
        db = get_db()
        sessions = (
            db.collection("users").document(user_id)
            .collection("chats")
            .order_by("last_active", direction="DESCENDING")
            .limit(5)
            .get()
        )
        messages: List[Dict[str, str]] = []
        for sess_doc in sessions:
            sess = sess_doc.to_dict() or {}
            sid = sess.get("session_id", sess_doc.id)
            if sid == current_session_id:
                continue
            docs = (
                db.collection("users").document(user_id)
                .collection("chats").document(sid)
                .collection("messages")
                .order_by("timestamp")
                .limit_to_last(4)
                .get()
            )
            for d in docs:
                data = d.to_dict() or {}
                messages.append({
                    "role": data.get("role", "user"),
                    "content": (data.get("content_summary") or data.get("content", ""))[:300],
                    "session": sid,
                })
            if len(messages) >= limit:
                break
        return messages[:limit]
    except Exception as exc:
        logger.warning("[memory_service] get_cross_session_messages failed: %s", exc)
        return []


# ── Session cleanup ──────────────────────────────────────────────────────────
async def cleanup_stale_sessions(user_id: str, max_age_days: int = _SESSION_STALE_DAYS) -> int:
    """Remove sessions older than max_age_days. Returns count of deleted sessions."""
    if not firebase_ready():
        return 0
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat(timespec="seconds")
        db = get_db()
        stale = (
            db.collection("users").document(user_id)
            .collection("chats")
            .where("last_active", "<", cutoff)
            .limit(20)
            .get()
        )
        deleted = 0
        for doc in stale:
            msgs = (
                db.collection("users").document(user_id)
                .collection("chats").document(doc.id)
                .collection("messages")
                .limit(100)
                .get()
            )
            batch = db.batch()
            for msg in msgs:
                batch.delete(msg.reference)
            batch.delete(doc.reference)
            batch.commit()
            deleted += 1
        if deleted:
            logger.info("[memory_service] cleaned up %d stale sessions for user=%s", deleted, user_id)
        return deleted
    except Exception as exc:
        logger.warning("[memory_service] cleanup_stale_sessions failed: %s", exc)
        return 0


__all__ = [
    "TravelPreferences",
    "ChatMessageDoc",
    "ConversationSummary",
    "MemoryContext",
    "save_message",
    "get_recent_messages",
    "get_all_session_messages",
    "get_cross_session_messages",
    "get_conversation_summary",
    "save_conversation_summary",
    "get_travel_preferences",
    "update_travel_preferences",
    "load_memory_context",
    "format_memory_for_prompt",
    "extract_preferences_from_message",
    "save_generated_plan",
    "cleanup_stale_sessions",
]
