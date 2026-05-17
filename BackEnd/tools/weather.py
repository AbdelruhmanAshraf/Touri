"""Weather tool — fetches real-time weather from OpenWeatherMap."""

import logging
import requests
from config import OPENWEATHER_API_KEY

logger = logging.getLogger(__name__)


def get_weather(city: str) -> str:
    """Fetch current weather for a city. Returns formatted string."""
    if not OPENWEATHER_API_KEY:
        return f"🌤 Weather data unavailable (no API key configured)"

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = requests.get(url, params={
            "q": f"{city},EG",
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        condition = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]

        return (
            f"🌤 **Current Weather in {city.title()}:**\n"
            f"- Condition: {condition}\n"
            f"- Temperature: {temp}°C (feels like {feels}°C)\n"
            f"- Humidity: {humidity}%"
        )
    except requests.exceptions.Timeout:
        return f"🌤 Weather data temporarily unavailable for {city}"
    except Exception as e:
        logger.warning(f"Weather API error for {city}: {e}")
        return f"🌤 Could not retrieve weather for {city}."
