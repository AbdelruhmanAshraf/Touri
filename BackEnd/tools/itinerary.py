"""
Itinerary Generator Tool — creates daily schedules.
"""

def create_itinerary(country: str, city: str, duration: int, tourism_type: str = "standard") -> dict:
    """Create a basic day-by-day itinerary template."""
    itinerary = {"city": city.title(), "country": country.title(), "duration": duration, "days": []}

    if tourism_type == "medical":
        for day in range(1, duration + 1):
            if day == 1:
                plan = {
                    "Morning": "Arrival & check-in. Initial medical consultation at the clinic/hospital.",
                    "Afternoon": "Rest at hotel/resort and light local lunch.",
                    "Evening": "Relaxed dinner near accommodation. Early sleep for recovery/preparation."
                }
            elif day == duration:
                plan = {
                    "Morning": "Final follow-up appointment & medical clearance.",
                    "Afternoon": "Light souvenir shopping or gentle walking tour.",
                    "Evening": "Farewell dinner & departure."
                }
            else:
                plan = {
                    "Morning": "Medical procedure / wellness treatment session.",
                    "Afternoon": "Rest & recovery or light cultural activity.",
                    "Evening": "Healthy dining at recommended restaurant."
                }
            itinerary["days"].append({"day": day, "plan": plan})
    else:
        for day in range(1, duration + 1):
            if day == 1:
                plan = {
                    "Morning": f"Arrival in {city.title()}, hotel check-in.",
                    "Afternoon": "Explore the local neighborhood and have lunch.",
                    "Evening": "Welcome dinner at a highly rated local restaurant."
                }
            elif day == duration:
                plan = {
                    "Morning": "Last-minute souvenir shopping at local markets.",
                    "Afternoon": "Relaxed lunch and prepare for departure.",
                    "Evening": "Departure."
                }
            else:
                plan = {
                    "Morning": "Visit top historical sites or museums.",
                    "Afternoon": "Cultural experience or guided tour.",
                    "Evening": "Experience local nightlife or a scenic dinner."
                }
            itinerary["days"].append({"day": day, "plan": plan})

    return itinerary


def format_itinerary_as_text(itinerary: dict) -> str:
    """Format the itinerary dictionary as Markdown text."""
    lines = [f"📅 **Suggested {itinerary['duration']}-Day Itinerary for {itinerary['city']}, {itinerary['country']}**\n"]
    
    for day in itinerary["days"]:
        lines.append(f"**Day {day['day']}**")
        for time_of_day, activity in day["plan"].items():
            lines.append(f"- **{time_of_day}:** {activity}")
        lines.append("")
        
    return "\n".join(lines)
