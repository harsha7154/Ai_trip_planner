"""
Trip service — orchestrates the complete trip planning pipeline:
  1. get_trip_places() → filter Excel data, build LLM context
  2. get_weather()     → async weather forecast
  3. generate_itinerary() → call LLM

Replaces the LangGraph pipeline from the notebook with clean async service calls.
LangGraph is optional and can be re-added if needed, but direct async calls are
faster and easier to debug in production.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Any

from loguru import logger

from app.core.exceptions import DataNotLoadedError, LLMError
from app.data.loader import DataLoader
from app.services.place_filter import get_trip_places
from app.services.weather import get_weather
from app.ai.llm import generate_itinerary


async def plan_trip(request: Dict[str, Any], loader: DataLoader) -> Dict[str, Any]:
    """
    Full trip planning pipeline. Returns dict with:
      - plan     : str (itinerary text)
      - images   : dict (place → image URLs)
      - weather  : list (daily forecasts)
      - metadata : dict (timing, districts, etc.)
    """
    if not loader.is_loaded():
        raise DataNotLoadedError("Place data not loaded. Check data/places.xlsx.")

    source      = str(request.get("start", "")).strip()
    destination = str(request.get("destination", "")).strip()
    days        = int(request.get("days", 1))
    budget      = request.get("budget", "Medium")
    mode        = request.get("mode", "Road")
    people      = int(request.get("people", 2))
    interests   = request.get("interests", [])

    t0 = time.monotonic()
    logger.info(f"Planning trip: {source} → {destination} | {days}d | {mode} | {people}p | {interests}")

    # ── Step 1 & 2: Run place filter and weather in parallel ─────────────────
    place_task   = get_trip_places(source, destination, interests, mode, days, loader)
    weather_task = get_weather(destination, days)

    (place_text, image_map), weather = await asyncio.gather(place_task, weather_task)

    logger.info(f"Places context built ({len(place_text)} chars), weather days: {len(weather)}")

    # ── Step 3: Generate itinerary ────────────────────────────────────────────
    state = {
        "start":       source,
        "destination": destination,
        "days":        days,
        "budget":      budget,
        "mode":        mode,
        "people":      people,
        "interests":   interests,
        "place_text":  place_text,
        "image_map":   image_map,
        "weather":     weather,
    }

    plan = await generate_itinerary(state)

    elapsed = round(time.monotonic() - t0, 2)
    logger.info(f"✅ Trip planned in {elapsed}s")

    return {
        "plan":    plan,
        "images":  image_map,
        "weather": weather,
        "metadata": {
            "elapsed_seconds": elapsed,
            "source":          source,
            "destination":     destination,
            "days":            days,
            "mode":            mode,
            "people":          people,
            "budget":          budget,
            "interests":       interests,
        },
    }
