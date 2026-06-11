"""
Integration tests for the Trip Planner API.
Run: pytest tests/ -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.data.loader import DataLoader


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_loader():
    loader = MagicMock(spec=DataLoader)
    loader.is_loaded.return_value = True
    loader.places = [
        {
            "place_name": "Lingaraj Temple",
            "district": "Khordha",
            "category": "Temple",
            "latitude": 20.2393,
            "longitude": 85.8340,
            "importance": "Largest temple in Bhubaneswar",
            "entry_ticket": "Free for Hindus",
            "activities_budget": "Temple tour (Free)",
            "map_link": "https://maps.google.com/?q=Lingaraj+Temple",
            "image_urls": "",
            "best_time": "October to March",
            "food_speciality": "Prasad",
            "otdc_stay": "Panthanivas Bhubaneswar",
            "cover_hours": 2.0,
        },
        {
            "place_name": "Puri Beach",
            "district": "Puri",
            "category": "Beach",
            "latitude": 19.7979,
            "longitude": 85.8245,
            "importance": "Famous golden beach",
            "entry_ticket": "Free",
            "activities_budget": "Swimming, sunbathing",
            "map_link": "https://maps.google.com/?q=Puri+Beach",
            "image_urls": "",
            "best_time": "November to February",
            "food_speciality": "Seafood",
            "otdc_stay": "Panthanivas Puri",
            "cover_hours": 3.0,
        },
    ]
    loader.get_districts.return_value = ["Khordha", "Puri"]
    loader.get_categories.return_value = ["Temple", "Beach"]
    loader.get_images.return_value = []
    loader.parse_image_urls.return_value = []
    return loader


@pytest.fixture
def client(mock_loader):
    app.state.data_loader = mock_loader
    with TestClient(app) as c:
        yield c


# ── Health check ──────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "running"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200


# ── Meta endpoints ────────────────────────────────────────────────────────────

def test_list_districts(client):
    r = client.get("/api/v1/districts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_categories(client):
    r = client.get("/api/v1/categories")
    assert r.status_code == 200


def test_list_interests(client):
    r = client.get("/api/v1/interests")
    assert r.status_code == 200
    data = r.json()
    assert "interests" in data
    assert "Temples" in data["interests"]


# ── Places ────────────────────────────────────────────────────────────────────

def test_list_places(client):
    r = client.get("/api/v1/places")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "places" in data


# ── Schema validation ─────────────────────────────────────────────────────────

def test_invalid_budget(client):
    payload = {
        "start": "Bhubaneswar",
        "destination": "Puri",
        "days": 3,
        "budget": "INVALID",
        "mode": "Road",
        "people": 2,
        "interests": [],
    }
    r = client.post("/api/v1/plan", json=payload)
    assert r.status_code == 422


def test_invalid_interest(client):
    payload = {
        "start": "Bhubaneswar",
        "destination": "Puri",
        "days": 3,
        "budget": "Medium",
        "mode": "Road",
        "people": 2,
        "interests": ["InvalidCategory"],
    }
    r = client.post("/api/v1/plan", json=payload)
    assert r.status_code == 422


# ── Unit tests ────────────────────────────────────────────────────────────────

def test_haversine():
    from app.geo.distance import haversine_km
    # Bhubaneswar to Puri ≈ 60 km straight line
    km = haversine_km(20.2961, 85.8245, 19.8043, 85.8174)
    assert 50 < km < 70


def test_matches_interest():
    from app.services.place_filter import matches_interest
    assert matches_interest("Temple", ["Temples"]) is True
    assert matches_interest("Beach", ["Beaches"]) is True
    assert matches_interest("Beach", ["Temples"]) is False
    assert matches_interest("Beach", []) is True   # no filter = all pass


def test_get_route_districts():
    from app.geo.distance import get_route_districts
    # Puri → Balasore should pass through multiple districts
    route = get_route_districts("Puri", "Balasore")
    assert isinstance(route, list)
    assert len(route) >= 1
