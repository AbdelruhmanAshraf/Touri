"""
Structured question schema for choice-based UI rendering.

The backend sends ``StructuredQuestion`` objects as part of ``needs_info``
responses. The frontend renders them as tappable chips, cards, or buttons
instead of expecting free-text replies.

Bilingual: every label carries both ``en`` and ``ar`` values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BilingualLabel(BaseModel):
    """A label with English and Arabic text."""
    en: str
    ar: str


class QuestionOption(BaseModel):
    """A single selectable option for a structured question."""
    id: str                          # Machine-readable value (e.g. "luxury")
    label: BilingualLabel            # Human-readable label
    emoji: Optional[str] = None      # Optional emoji prefix
    description: Optional[BilingualLabel] = None  # Optional longer description


class StructuredQuestion(BaseModel):
    """
    A single structured question sent to the frontend for chip/card rendering.

    The frontend reads ``field`` to know which requirement this answers,
    and ``options`` to render selectable UI elements.
    """
    field: str                       # The requirement field (e.g. "destination", "budget")
    question: BilingualLabel         # The question text
    options: List[QuestionOption]    # Selectable choices
    input_type: Literal["single_select", "multi_select", "text_input", "number_input"] = "single_select"
    required: bool = True
    allow_custom: bool = False       # Whether to show a text fallback


class QuestionSet(BaseModel):
    """One or more structured questions bundled in a single response."""
    questions: List[StructuredQuestion]
    intro_text: BilingualLabel       # Friendly intro message
    # Total fields still missing after these questions are answered
    remaining_fields: int = 0


# ── Pre-built question templates ─────────────────────────────────────────────

DESTINATION_QUESTION = StructuredQuestion(
    field="destination",
    question=BilingualLabel(
        en="Which city or region would you like to visit?",
        ar="ما المدينة أو المنطقة التي تود زيارتها؟",
    ),
    options=[
        QuestionOption(id="cairo", label=BilingualLabel(en="Cairo", ar="القاهرة"), emoji="🏛️"),
        QuestionOption(id="alexandria", label=BilingualLabel(en="Alexandria", ar="الإسكندرية"), emoji="🌊"),
        QuestionOption(id="luxor", label=BilingualLabel(en="Luxor", ar="الأقصر"), emoji="⛩️"),
        QuestionOption(id="aswan", label=BilingualLabel(en="Aswan", ar="أسوان"), emoji="🌅"),
        QuestionOption(id="hurghada", label=BilingualLabel(en="Hurghada", ar="الغردقة"), emoji="🏖️"),
        QuestionOption(id="sharm", label=BilingualLabel(en="Sharm El Sheikh", ar="شرم الشيخ"), emoji="🤿"),
    ],
    allow_custom=True,
)

DURATION_QUESTION = StructuredQuestion(
    field="duration",
    question=BilingualLabel(
        en="How many days are you planning?",
        ar="كم يوم تخطط لقضائها؟",
    ),
    options=[
        QuestionOption(id="3", label=BilingualLabel(en="3 days", ar="3 أيام"), emoji="📅"),
        QuestionOption(id="5", label=BilingualLabel(en="5 days", ar="5 أيام"), emoji="📅"),
        QuestionOption(id="7", label=BilingualLabel(en="1 week", ar="أسبوع"), emoji="📅"),
        QuestionOption(id="10", label=BilingualLabel(en="10 days", ar="10 أيام"), emoji="📅"),
        QuestionOption(id="14", label=BilingualLabel(en="2 weeks", ar="أسبوعين"), emoji="📅"),
    ],
    allow_custom=True,
)

BUDGET_QUESTION = StructuredQuestion(
    field="budget",
    question=BilingualLabel(
        en="What's your preferred budget level?",
        ar="ما مستوى الميزانية المفضل لديك؟",
    ),
    options=[
        QuestionOption(
            id="economy",
            label=BilingualLabel(en="Economy", ar="اقتصادي"),
            emoji="💰",
            description=BilingualLabel(en="Budget-friendly options", ar="خيارات اقتصادية"),
        ),
        QuestionOption(
            id="mid_range",
            label=BilingualLabel(en="Mid-range", ar="متوسط"),
            emoji="💎",
            description=BilingualLabel(en="Comfortable balance", ar="توازن مريح"),
        ),
        QuestionOption(
            id="luxury",
            label=BilingualLabel(en="Luxury", ar="فاخر"),
            emoji="👑",
            description=BilingualLabel(en="Premium experiences", ar="تجارب فاخرة"),
        ),
    ],
)

PARTY_SIZE_QUESTION = StructuredQuestion(
    field="party_size",
    question=BilingualLabel(
        en="How many travellers?",
        ar="كم عدد المسافرين؟",
    ),
    options=[
        QuestionOption(id="1", label=BilingualLabel(en="Solo", ar="فردي"), emoji="🧍"),
        QuestionOption(id="2", label=BilingualLabel(en="Couple", ar="ثنائي"), emoji="👫"),
        QuestionOption(id="4", label=BilingualLabel(en="Family (4)", ar="عائلة (4)"), emoji="👨‍👩‍👧‍👦"),
        QuestionOption(id="6", label=BilingualLabel(en="Group (6+)", ar="مجموعة (6+)"), emoji="👥"),
    ],
    allow_custom=True,
    input_type="single_select",
)

TRIP_TYPE_QUESTION = StructuredQuestion(
    field="trip_type",
    question=BilingualLabel(
        en="What type of trip are you looking for?",
        ar="ما نوع الرحلة التي تبحث عنها؟",
    ),
    options=[
        QuestionOption(id="luxury", label=BilingualLabel(en="Luxury", ar="فاخرة"), emoji="👑"),
        QuestionOption(id="adventure", label=BilingualLabel(en="Adventure", ar="مغامرة"), emoji="🧗"),
        QuestionOption(id="relaxation", label=BilingualLabel(en="Relaxation", ar="استرخاء"), emoji="🧘"),
        QuestionOption(id="historical", label=BilingualLabel(en="Historical", ar="تاريخية"), emoji="🏛️"),
        QuestionOption(id="medical", label=BilingualLabel(en="Medical", ar="علاجية"), emoji="🏥"),
        QuestionOption(id="family", label=BilingualLabel(en="Family", ar="عائلية"), emoji="👨‍👩‍👧"),
    ],
)

TRANSPORTATION_QUESTION = StructuredQuestion(
    field="transportation",
    question=BilingualLabel(
        en="How do you prefer to get around?",
        ar="كيف تفضل التنقل؟",
    ),
    options=[
        QuestionOption(id="walking", label=BilingualLabel(en="Walking", ar="مشياً"), emoji="🚶"),
        QuestionOption(id="uber", label=BilingualLabel(en="Uber / Taxi", ar="أوبر / تاكسي"), emoji="🚕"),
        QuestionOption(id="rental", label=BilingualLabel(en="Rental Car", ar="سيارة مستأجرة"), emoji="🚗"),
        QuestionOption(id="public", label=BilingualLabel(en="Public Transport", ar="مواصلات عامة"), emoji="🚌"),
    ],
)

HOTEL_STYLE_QUESTION = StructuredQuestion(
    field="hotel_style",
    question=BilingualLabel(
        en="What's your preferred accommodation?",
        ar="ما نوع الإقامة المفضل لديك؟",
    ),
    options=[
        QuestionOption(id="hotel", label=BilingualLabel(en="Hotel", ar="فندق"), emoji="🏨"),
        QuestionOption(id="resort", label=BilingualLabel(en="Resort", ar="منتجع"), emoji="🏖️"),
        QuestionOption(id="apartment", label=BilingualLabel(en="Apartment", ar="شقة"), emoji="🏠"),
        QuestionOption(id="boutique", label=BilingualLabel(en="Boutique", ar="بوتيك"), emoji="✨"),
        QuestionOption(id="beachfront", label=BilingualLabel(en="Beachfront", ar="على الشاطئ"), emoji="🌊"),
    ],
)

ACTIVITIES_QUESTION = StructuredQuestion(
    field="activities",
    question=BilingualLabel(
        en="What activities interest you?",
        ar="ما الأنشطة التي تهمك؟",
    ),
    options=[
        QuestionOption(id="sightseeing", label=BilingualLabel(en="Sightseeing", ar="مشاهدة المعالم"), emoji="📸"),
        QuestionOption(id="diving", label=BilingualLabel(en="Diving & Snorkeling", ar="غوص وسنوركل"), emoji="🤿"),
        QuestionOption(id="desert_safari", label=BilingualLabel(en="Desert Safari", ar="سفاري صحراوي"), emoji="🐫"),
        QuestionOption(id="food_tour", label=BilingualLabel(en="Food Tour", ar="جولة طعام"), emoji="🍽️"),
        QuestionOption(id="shopping", label=BilingualLabel(en="Shopping", ar="تسوق"), emoji="🛍️"),
        QuestionOption(id="spa", label=BilingualLabel(en="Spa & Wellness", ar="سبا واستجمام"), emoji="💆"),
    ],
    input_type="multi_select",
    required=False,
)

DIETARY_QUESTION = StructuredQuestion(
    field="dietary",
    question=BilingualLabel(
        en="Any dietary requirements?",
        ar="هل لديك متطلبات غذائية؟",
    ),
    options=[
        QuestionOption(id="none", label=BilingualLabel(en="None", ar="لا يوجد"), emoji="✅"),
        QuestionOption(id="vegetarian", label=BilingualLabel(en="Vegetarian", ar="نباتي"), emoji="🥬"),
        QuestionOption(id="vegan", label=BilingualLabel(en="Vegan", ar="نباتي صرف"), emoji="🌱"),
        QuestionOption(id="halal", label=BilingualLabel(en="Halal", ar="حلال"), emoji="🕌"),
        QuestionOption(id="gluten_free", label=BilingualLabel(en="Gluten-free", ar="خالي من الغلوتين"), emoji="🌾"),
    ],
    input_type="multi_select",
    required=False,
)

START_DATE_QUESTION = StructuredQuestion(
    field="start_date",
    question=BilingualLabel(
        en="When are you planning to travel?",
        ar="متى تخطط للسفر؟",
    ),
    options=[
        QuestionOption(id="this_week", label=BilingualLabel(en="This week", ar="هذا الأسبوع"), emoji="📅"),
        QuestionOption(id="next_week", label=BilingualLabel(en="Next week", ar="الأسبوع القادم"), emoji="📅"),
        QuestionOption(id="this_month", label=BilingualLabel(en="This month", ar="هذا الشهر"), emoji="📅"),
        QuestionOption(id="next_month", label=BilingualLabel(en="Next month", ar="الشهر القادم"), emoji="📅"),
        QuestionOption(id="flexible", label=BilingualLabel(en="Flexible", ar="مرن"), emoji="🤷"),
    ],
    allow_custom=True,
    required=False,
)

# Registry for quick lookup
QUESTION_REGISTRY: Dict[str, StructuredQuestion] = {
    "destination": DESTINATION_QUESTION,
    "duration": DURATION_QUESTION,
    "budget": BUDGET_QUESTION,
    "party_size": PARTY_SIZE_QUESTION,
    "trip_type": TRIP_TYPE_QUESTION,
    "transportation": TRANSPORTATION_QUESTION,
    "hotel_style": HOTEL_STYLE_QUESTION,
    "activities": ACTIVITIES_QUESTION,
    "dietary": DIETARY_QUESTION,
    "start_date": START_DATE_QUESTION,
}


__all__ = [
    "BilingualLabel",
    "QuestionOption",
    "StructuredQuestion",
    "QuestionSet",
    "QUESTION_REGISTRY",
]
