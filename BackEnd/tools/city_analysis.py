"""
City Analysis Tool — analyzes hotels, attractions, restaurants, events, and medical centers for a given city.
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# _data[country][dataset_name] = pd.DataFrame
_data: dict = {}

def load_data(datasets_dir: Path):
    """Load all CSV datasets into memory for all supported countries."""
    global _data
    from config import get_dataset_files
    from data.countries import SUPPORTED_COUNTRIES

    for country in SUPPORTED_COUNTRIES.keys():
        _data[country] = {}
        files = get_dataset_files(country)
        for name, path in files.items():
            if path.exists():
                try:
                    for enc in ("utf-8", "latin-1", "cp1252"):
                        try:
                            df = pd.read_csv(path, encoding=enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        logger.warning(f"Could not decode {path.name}")
                        _data[country][name] = pd.DataFrame()
                        continue
                    # Normalize city column
                    for col in ["City", "city"]:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.strip().str.lower()
                    _data[country][name] = df
                    logger.info(f"✅ {country}/{name}: {len(df)} records")
                except Exception as e:
                    logger.warning(f"Failed to load {path.name}: {e}")
                    _data[country][name] = pd.DataFrame()
            else:
                _data[country][name] = pd.DataFrame()

def analyze_city(country: str, city: str, tourism_type: str = "standard") -> str:
    """
    Analyze city data and return a formatted summary.
    """
    country = country.lower()
    city_lower = city.strip().lower()
    c_data = _data.get(country, {})
    from data.countries import SUPPORTED_COUNTRIES
    currency = SUPPORTED_COUNTRIES.get(country, {}).get("currency", "USD")

    lines = [f"📍 **City Analysis: {city.title()}, {country.title()}**\n"]

    # Medical Centers (if medical tourism)
    if tourism_type == "medical":
        med_centers = c_data.get("medical_centers", pd.DataFrame())
        if not med_centers.empty:
            city_med = med_centers[med_centers.get("City", pd.Series()).astype(str).str.lower() == city_lower]
            if not city_med.empty:
                lines.append(f"🏥 **Medical Centers ({len(city_med)} available)**")
                for _, m in city_med.head(3).iterrows():
                    name = m.get("Name", "Clinic")
                    rating = m.get("Rating", "N/A")
                    lines.append(f"  • {name} (⭐ {rating})")
            else:
                lines.append("🏥 **Medical Centers:** Limited data")
        lines.append("")

    # Hotels
    hotels = c_data.get("hotels", pd.DataFrame())
    if not hotels.empty:
        city_hotels = hotels[hotels.get("City", pd.Series()).astype(str).str.lower() == city_lower]
        if not city_hotels.empty:
            price_col = next((c for c in city_hotels.columns if "Price" in c), None)
            if price_col:
                avg_price = pd.to_numeric(city_hotels[price_col], errors="coerce").mean()
                lines.append(f"🏨 **Hotels ({len(city_hotels)} available)**")
                if not pd.isna(avg_price):
                    lines.append(f"  Avg price/night: {avg_price:,.0f} {currency}")
            top = city_hotels.nlargest(3, "Rating") if "Rating" in city_hotels.columns else city_hotels.head(3)
            for _, h in top.iterrows():
                name = h.get("Hotel Name", h.get("Name", "Hotel"))
                rating = h.get("Rating", "N/A")
                lines.append(f"  • {name} (⭐ {rating})")
        else:
            lines.append("🏨 **Accommodation:** Limited data available")
    lines.append("")

    # Attractions
    attractions = c_data.get("attractions", pd.DataFrame())
    if not attractions.empty:
        city_attr = attractions[attractions.get("City", pd.Series()).astype(str).str.lower() == city_lower]
        if not city_attr.empty:
            lines.append(f"🏛 **Attractions ({len(city_attr)} sites)**")
            rating_col = next((c for c in ["Rating", "rating", "Score"] if c in city_attr.columns), None)
            if rating_col:
                top = city_attr.nlargest(5, rating_col)
                lines.append("⭐ Must-Visit Attractions:")
                for _, a in top.iterrows():
                    name = a.get("Attraction", a.get("Name", "Attraction"))
                    rating = a.get(rating_col, "N/A")
                    lines.append(f"  • {name} ({rating}/5)")
    lines.append("")

    # Restaurants
    restaurants = c_data.get("restaurants", pd.DataFrame())
    if not restaurants.empty:
        city_col = next((c for c in ["City", "city"] if c in restaurants.columns), None)
        city_rest = restaurants[restaurants[city_col].astype(str).str.lower() == city_lower] if city_col else restaurants
        if not city_rest.empty:
            lines.append(f"🍽 **Dining ({len(city_rest)} options)**")
            rating_col = next((c for c in ["User Rating", "Rating", "rating"] if c in city_rest.columns), None)
            if rating_col:
                top = city_rest.nlargest(3, rating_col)
                lines.append("⭐ Top Rated Restaurants:")
                for _, r in top.iterrows():
                    name = r.get("Name", r.get("Restaurant_Name", "Restaurant"))
                    rating = r.get(rating_col, "N/A")
                    lines.append(f"  • {name} ({rating}/5)")
    lines.append("")

    return "\n".join(lines)
