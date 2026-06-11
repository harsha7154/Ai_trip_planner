"""
Pydantic schemas for API request/response validation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    start: str = Field(..., min_length=2, max_length=100, description="Source city/place")
    destination: str = Field(..., min_length=2, max_length=100, description="Destination city/place")
    days: int = Field(..., ge=1, le=15, description="Number of trip days")
    budget: str = Field("Medium", description="Budget tier: Budget | Medium | Luxury")
    mode: str = Field("Road", description="Travel mode: Road | Train | Flight")
    people: int = Field(2, ge=1, le=20, description="Number of travellers")
    interests: List[str] = Field(default_factory=list, description="Interest categories")

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v: str) -> str:
        allowed = {"Budget", "Medium", "Luxury"}
        if v not in allowed:
            raise ValueError(f"budget must be one of {allowed}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = {"Road", "Train", "Flight"}
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v: List[str]) -> List[str]:
        valid = {
            "Temples", "Beaches", "Heritage", "Nature", "Trekking",
            "Adventure", "Food", "Eco-Tourism", "Culture", "Wildlife",
            "Nature Camps",
        }
        for i in v:
            if i not in valid:
                raise ValueError(f"'{i}' is not a valid interest. Choose from {valid}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "start": "Bhubaneswar",
                "destination": "Puri",
                "days": 3,
                "budget": "Medium",
                "mode": "Road",
                "people": 2,
                "interests": ["Temples", "Beaches"],
            }
        }
    }


class WeatherDay(BaseModel):
    date: str
    condition: str
    temp_c: float
    feels_c: float
    humidity: int
    wind_kmh: float


class PlaceInfo(BaseModel):
    place_name: str
    district: Optional[str] = None
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_urls: List[str] = Field(default_factory=list)


class TripResponse(BaseModel):
    success: bool = True
    plan: str
    images: Dict[str, List[str]] = Field(default_factory=dict)
    weather: List[WeatherDay] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    places_loaded: int
    data_source: str


class PlacesFilterRequest(BaseModel):
    district: Optional[str] = None
    category: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    limit: int = Field(50, ge=1, le=200)


class PlacesResponse(BaseModel):
    total: int
    places: List[Dict[str, Any]]
