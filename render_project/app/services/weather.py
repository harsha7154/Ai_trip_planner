"""
Weather service — async OpenWeather 5-day forecast API.
Falls back gracefully (returns [] on any failure).
"""
from __future__ import annotations

from typing import List, Dict, Any

import httpx
from loguru import logger

from app.core.config import settings
from app.geo.constants import WEATHER_CITY_MAP


async def get_weather(city: str, days: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch OpenWeather 5-day forecast for a city.
    Handles Odisha city aliases, multi-step fallback (with/without country code).
    Returns list of daily forecast dicts (max min(days, 5)).
    Returns [] on any failure — weather is optional, never crashes the trip plan.
    """
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.warning("[Weather] No API key configured — skipping weather fetch.")
        return []

    key    = city.lower().strip()
    lookup = WEATHER_CITY_MAP.get(key, city.strip())

    async def fetch(city_name: str, country: str = "IN") -> httpx.Response:
        q   = f"{city_name},{country}" if country else city_name
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?q={q}&appid={api_key}&units=metric"
        )
        async with httpx.AsyncClient(timeout=6.0) as client:
            return await client.get(url)

    try:
        r = await fetch(lookup, "IN")
        if r.status_code == 404:
            r = await fetch(lookup, "")
        if r.status_code == 404 and lookup.lower() != key:
            r = await fetch(city.strip(), "IN")
            if r.status_code == 404:
                r = await fetch(city.strip(), "")

        if r.status_code != 200:
            logger.warning(f"[Weather] HTTP {r.status_code} for '{city}' (tried '{lookup}')")
            return []

        daily, seen = [], set()
        for item in r.json().get("list", []):
            d = item["dt_txt"].split(" ")[0]
            if d not in seen:
                daily.append({
                    "date":      d,
                    "condition": item["weather"][0]["description"].capitalize(),
                    "temp_c":    round(item["main"]["temp"], 1),
                    "feels_c":   round(item["main"]["feels_like"], 1),
                    "humidity":  item["main"]["humidity"],
                    "wind_kmh":  round(item["wind"]["speed"] * 3.6, 1),
                })
                seen.add(d)
            if len(daily) >= min(days, 5):
                break

        if not daily:
            logger.warning(f"[Weather] Empty list for '{lookup}'")
        return daily

    except Exception as e:
        logger.warning(f"[Weather] Exception for '{city}': {e}")
        return []
