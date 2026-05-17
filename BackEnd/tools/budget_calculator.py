"""
Budget Calculator Tool — estimates costs for a trip.
"""

from data.countries import SUPPORTED_COUNTRIES

def calculate_budget(
    country: str,
    city: str,
    duration: int,
    budget_range: str = "mid-range",
    num_travelers: int = 1,
    tourism_type: str = "standard",
    total_budget_usd: float = 0.0
) -> dict:
    """Calculate an estimated budget for a trip."""
    
    c_info = SUPPORTED_COUNTRIES.get(country.lower(), SUPPORTED_COUNTRIES["egypt"])
    usd_rate = c_info["usd_rate"]
    currency = c_info["currency"]

    # Base daily costs per person in USD
    base_costs_usd = {
        "economy": {"hotel": 30, "food": 20, "transport": 10, "activities": 15},
        "mid-range": {"hotel": 80, "food": 50, "transport": 25, "activities": 40},
        "luxury": {"hotel": 200, "food": 120, "transport": 60, "activities": 100},
    }

    daily = base_costs_usd.get(budget_range, base_costs_usd["mid-range"])
    
    # Calculate totals in USD
    hotel_total_usd = daily["hotel"] * duration * ((num_travelers + 1) // 2)  # 2 pax per room
    food_total_usd = daily["food"] * duration * num_travelers
    transport_total_usd = daily["transport"] * duration * num_travelers
    activities_total_usd = daily["activities"] * duration * num_travelers
    
    medical_fees_usd = 0.0
    if tourism_type == "medical":
        # Add baseline medical consultation/procedure fees
        med_costs = {"economy": 300, "mid-range": 800, "luxury": 2000}
        medical_fees_usd = med_costs.get(budget_range, 800) * num_travelers

    total_usd = hotel_total_usd + food_total_usd + transport_total_usd + activities_total_usd + medical_fees_usd

    # Convert to local currency
    return {
        "duration": duration,
        "num_travelers": num_travelers,
        "budget_range": budget_range,
        "currency": currency,
        "usd_rate": usd_rate,
        "hotel_local": round(hotel_total_usd * usd_rate),
        "hotel_usd": round(hotel_total_usd),
        "food_local": round(food_total_usd * usd_rate),
        "food_usd": round(food_total_usd),
        "transport_local": round(transport_total_usd * usd_rate),
        "transport_usd": round(transport_total_usd),
        "activities_local": round(activities_total_usd * usd_rate),
        "activities_usd": round(activities_total_usd),
        "medical_local": round(medical_fees_usd * usd_rate),
        "medical_usd": round(medical_fees_usd),
        "total_local": round(total_usd * usd_rate),
        "total_usd": round(total_usd),
        "user_budget_usd": total_budget_usd,
        "is_over_budget": total_budget_usd > 0 and total_usd > total_budget_usd
    }

def format_budget_as_text(budget_dict: dict) -> str:
    """Format the budget dictionary as Markdown text."""
    currency = budget_dict["currency"]
    
    lines = [
        f"**Estimated Budget for {budget_dict['duration']} days ({budget_dict['num_travelers']} travelers) - {budget_dict['budget_range'].title()}**\n",
        "| Category | Cost (Local) | Cost (USD) |",
        "|----------|--------------|------------|",
        f"| 🏨 Accommodation | {budget_dict['hotel_local']:,} {currency} | ${budget_dict['hotel_usd']:,} |",
        f"| 🍽️ Food & Dining | {budget_dict['food_local']:,} {currency} | ${budget_dict['food_usd']:,} |",
        f"| 🚗 Transportation | {budget_dict['transport_local']:,} {currency} | ${budget_dict['transport_usd']:,} |",
        f"| 🏛️ Activities | {budget_dict['activities_local']:,} {currency} | ${budget_dict['activities_usd']:,} |"
    ]
    
    if budget_dict.get("medical_usd", 0) > 0:
        lines.append(f"| 🏥 Medical Fees | {budget_dict['medical_local']:,} {currency} | ${budget_dict['medical_usd']:,} |")
        
    lines.extend([
        "| **Total Estimated** | **{} {}** | **${}** |".format(
            f"{budget_dict['total_local']:,}", currency, f"{budget_dict['total_usd']:,}"
        )
    ])
    
    if budget_dict["user_budget_usd"] > 0:
        lines.append(f"\n*Your Total Budget: ${budget_dict['user_budget_usd']:,}*")
        if budget_dict["is_over_budget"]:
            lines.append("⚠️ **Warning: Estimated cost exceeds your budget. Consider adjusting duration or style.**")
        else:
            lines.append("✅ **Great! This plan is well within your budget.**")
            
    return "\n".join(lines)
