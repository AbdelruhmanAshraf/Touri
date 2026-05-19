from enum import Enum
from pydantic import BaseModel
from typing import List, Any, Optional

class UITriggerType(str, Enum):
    DATE_PICKER = "date_picker"
    RANGE_SLIDER = "range_slider"
    TRAVELER_COUNTER = "traveler_counter"
    HOTEL_CARDS = "hotel_cards"
    DESTINATION_CAROUSEL = "destination_carousel"
    ACTIVITY_GRID = "activity_grid"
    MAP_SELECTOR = "map_selector"
    TIMELINE_CARDS = "timeline_cards"
    BUDGET_SELECTOR = "budget_selector"
    CHIPS = "chips" # Legacy/Basic

class UITrigger(BaseModel):
    type: UITriggerType
    data: Optional[Any] = None
    label: Optional[str] = None
    required: bool = False
