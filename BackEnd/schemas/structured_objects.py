from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class HotelRecommendation(BaseModel):
    id: str
    name: str
    rating: float
    price_per_night: float
    amenities: List[str]
    description: str
    image_url: Optional[str] = None

class ActivityRecommendation(BaseModel):
    id: str
    title: str
    duration_hours: float
    cost: float
    location: str
    description: str
    tags: List[str]
    done: bool = False

class DayPlan(BaseModel):
    day_number: int
    morning_activities: List[ActivityRecommendation]
    afternoon_activities: List[ActivityRecommendation]
    evening_activities: List[ActivityRecommendation]
    hotel: Optional[HotelRecommendation] = None

class BudgetBreakdown(BaseModel):
    accommodation: float
    activities: float
    food: float
    transport: float
    total: float
    remaining_budget: Optional[float] = None

class TransportationPlan(BaseModel):
    options: List[Dict[str, Any]]
    estimated_cost: float

class TripPlan(BaseModel):
    destination: str
    start_date: str
    end_date: str
    days: List[DayPlan]
    budget: BudgetBreakdown
    transportation: Optional[TransportationPlan] = None
