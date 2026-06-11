"""
API routes — all HTTP endpoints for the Odisha Trip Planner.
"""
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from app.schemas.trip import (
    TripRequest,
    TripResponse,
    ErrorResponse,
    PlacesFilterRequest,
    PlacesResponse,
)
from app.services.trip import plan_trip
from app.services.weather import get_weather
from app.core.exceptions import DataNotLoadedError, LLMError

router = APIRouter()


def _get_loader(request: Request):
    loader = getattr(request.app.state, "data_loader", None)
    if loader is None or not loader.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data not loaded. Check data/places.xlsx and restart the server.",
        )
    return loader


# ── Trip planning ─────────────────────────────────────────────────────────────

@router.post(
    "/plan",
    response_model=TripResponse,
    summary="Generate an AI trip itinerary",
    tags=["Trip Planning"],
)
async def api_plan_trip(data: TripRequest, request: Request):
    """
    Main endpoint — generates a complete day-wise itinerary.

    - Filters places from Excel by route + interests
    - Fetches live weather
    - Calls Groq LLM (Gemini fallback) to generate the itinerary
    """
    loader = _get_loader(request)
    try:
        result = await plan_trip(data.model_dump(), loader)
        return TripResponse(
            success=True,
            plan=result["plan"],
            images=result["images"],
            weather=result["weather"],
            metadata=result["metadata"],
        )
    except DataNotLoadedError as e:
        logger.error(f"DataNotLoadedError: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except LLMError as e:
        logger.error(f"LLMError: {e}")
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in /plan: {e}")
        raise HTTPException(status_code=500, detail="Internal server error. Check logs.")


# ── Places explorer ───────────────────────────────────────────────────────────

@router.get(
    "/places",
    response_model=PlacesResponse,
    summary="List all places",
    tags=["Places"],
)
async def list_places(request: Request, limit: int = 50):
    """Return up to `limit` places from the dataset."""
    loader = _get_loader(request)
    places = loader.places[:limit]
    return PlacesResponse(total=len(loader.places), places=places)


@router.post(
    "/places/filter",
    response_model=PlacesResponse,
    summary="Filter places by district/category/interests",
    tags=["Places"],
)
async def filter_places(body: PlacesFilterRequest, request: Request):
    """Filter the place dataset by district, category, and interests."""
    from app.services.place_filter import matches_interest
    loader = _get_loader(request)

    results = []
    for p in loader.places:
        if body.district and str(p.get("district", "")).strip().lower() != body.district.lower():
            continue
        if body.category and str(p.get("category", "")).strip().lower() != body.category.lower():
            continue
        if body.interests and not matches_interest(str(p.get("category", "")), body.interests):
            continue
        results.append(p)

    return PlacesResponse(total=len(results), places=results[: body.limit])


@router.get(
    "/places/{place_name}/images",
    summary="Get images for a specific place",
    tags=["Places"],
)
async def get_place_images(place_name: str, request: Request):
    loader = _get_loader(request)
    imgs = loader.get_images(place_name)
    return {"place_name": place_name, "images": imgs}


# ── Districts & categories ────────────────────────────────────────────────────

@router.get(
    "/districts",
    response_model=List[str],
    summary="List all districts in the dataset",
    tags=["Meta"],
)
async def list_districts(request: Request):
    loader = _get_loader(request)
    return loader.get_districts()


@router.get(
    "/categories",
    response_model=List[str],
    summary="List all place categories",
    tags=["Meta"],
)
async def list_categories(request: Request):
    loader = _get_loader(request)
    return loader.get_categories()


@router.get(
    "/interests",
    summary="List supported interest types",
    tags=["Meta"],
)
async def list_interests():
    from app.geo.constants import INTEREST_CATS
    return {"interests": list(INTEREST_CATS.keys())}


# ── Weather ───────────────────────────────────────────────────────────────────

@router.get(
    "/weather/{city}",
    summary="Get weather forecast for a city",
    tags=["Weather"],
)
async def get_city_weather(city: str, days: int = 3):
    """Fetch OpenWeather 5-day forecast for any Odisha city."""
    weather = await get_weather(city, days)
    return {"city": city, "days": len(weather), "forecast": weather}
