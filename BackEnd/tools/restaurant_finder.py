"""
Restaurant Finder Tool — filters local datasets.
"""

import pandas as pd

def find_restaurants(country: str, city: str, dietary: str = None) -> str:
    """Find restaurants in a city, optionally filtered by dietary needs."""
    from tools.city_analysis import _data
    country = country.lower()
    city_lower = city.strip().lower()
    
    restaurants = _data.get(country, {}).get("restaurants", pd.DataFrame())
    if restaurants.empty:
        return f"No restaurant data currently available for {city}."
        
    city_col = next((c for c in ["City", "city"] if c in restaurants.columns), None)
    if city_col:
        city_rest = restaurants[restaurants[city_col].astype(str).str.lower() == city_lower]
    else:
        city_rest = restaurants
        
    if city_rest.empty:
        return f"No specific dining data found for {city}."
        
    if dietary:
        d_lower = dietary.lower()
        cuisine_col = next((c for c in ["Cuisine Type", "Cuisine", "cuisine"] if c in city_rest.columns), None)
        if cuisine_col:
            # simple text match filter
            filtered = city_rest[city_rest[cuisine_col].astype(str).str.lower().str.contains(d_lower, na=False)]
            if not filtered.empty:
                city_rest = filtered
                
    rating_col = next((c for c in ["User Rating", "Rating", "rating"] if c in city_rest.columns), None)
    if rating_col:
        top = city_rest.nlargest(5, rating_col)
    else:
        top = city_rest.head(5)
        
    lines = [f"🍽️ **Dining Options in {city.title()}**"]
    if dietary:
        lines[0] += f" (Preference: {dietary})"
        
    for _, r in top.iterrows():
        name = r.get("Name", r.get("Restaurant_Name", "Restaurant"))
        rating = r.get(rating_col, "N/A")
        cuisine = r.get("Cuisine Type", r.get("Cuisine", ""))
        lines.append(f"  • **{name}** (⭐ {rating}) - {cuisine}")
        
    return "\n".join(lines)
