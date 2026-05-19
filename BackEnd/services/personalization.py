from typing import Dict, Any, List

class PersonalizationEngine:
    def __init__(self):
        self.base_profile = {
            "luxury_score": 0.5,
            "adventure_score": 0.5,
            "relaxation_score": 0.5,
            "food_exploration_score": 0.5,
            "spontaneity_score": 0.5
        }
    
    def update_profile(self, user_id: str, new_interactions: List[Dict[str, Any]]) -> Dict[str, float]:
        # Placeholder for complex behavioral learning computation
        current_profile = self.base_profile.copy()
        for interaction in new_interactions:
            if "luxury" in interaction.get("content", "").lower():
                current_profile["luxury_score"] = min(1.0, current_profile["luxury_score"] + 0.1)
            if "hike" in interaction.get("content", "").lower():
                current_profile["adventure_score"] = min(1.0, current_profile["adventure_score"] + 0.1)
        return current_profile
