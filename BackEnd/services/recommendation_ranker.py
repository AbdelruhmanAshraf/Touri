from typing import List, Dict, Any
from schemas.structured_objects import HotelRecommendation, ActivityRecommendation

class RecommendationRanker:
    def rank_hotels(self, hotels: List[HotelRecommendation], user_profile: Dict[str, float], budget_limit: float) -> List[HotelRecommendation]:
        """Rank hotels dynamically based on personalization scores and user budget limits."""
        def score_hotel(hotel: HotelRecommendation) -> float:
            score = hotel.rating
            if hotel.price_per_night > budget_limit:
                # Penalty for being over budget
                score -= (hotel.price_per_night - budget_limit) * 0.05
            if user_profile.get("luxury_score", 0.5) > 0.7 and hotel.rating >= 4.5:
                # Bonus for luxury seekers looking at highly rated hotels
                score += 2.0
            return score

        return sorted(hotels, key=score_hotel, reverse=True)
    
    def rank_activities(self, activities: List[ActivityRecommendation], user_profile: Dict[str, float]) -> List[ActivityRecommendation]:
        """Rank activities dynamically based on personalization scores (adventure, relaxation, etc.)."""
        def score_activity(activity: ActivityRecommendation) -> float:
            score = 5.0
            tags = [tag.lower() for tag in activity.tags]
            if "adventure" in tags:
                score += user_profile.get("adventure_score", 0.5) * 2
            if "relaxation" in tags:
                score += user_profile.get("relaxation_score", 0.5) * 2
            if "food" in tags:
                score += user_profile.get("food_exploration_score", 0.5) * 2
            return score
        
        return sorted(activities, key=score_activity, reverse=True)
