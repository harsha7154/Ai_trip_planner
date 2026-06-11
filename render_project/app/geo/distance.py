"""
Geo distance service.
- Haversine used for bulk filtering / internal sorting (fast, free)
- OSRM public API used for real road distances (no API key required)
- Geoapify Routing API as secondary fallback (if OSRM fails)
- Haversine × road_factor as final fallback
- In-memory cache with TTL to avoid repeated API calls

FLIGHT MODE:
- Source city → nearest Odisha airport (by haversine)
- Airport → destination: real road distance
"""
from __future__ import annotations

import math
import time
from typing import Dict, Tuple, Optional, List, Any

import httpx
from loguru import logger

from app.core.config import settings
from app.geo.constants import CITY_COORDS, DISTRICT_ADJACENT
from app.data.loader import DataLoader


# ── All valid Odisha district names ──────────────────────────────────────────
ODISHA_DISTRICTS: set = {
    "Angul", "Balangir", "Balasore", "Bargarh", "Bhadrak", "Boudh",
    "Cuttack", "Deogarh", "Dhenkanal", "Gajapati", "Ganjam",
    "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi", "Kandhamal",
    "Kendrapara", "Keonjhar", "Khordha", "Koraput", "Malkangiri",
    "Mayurbhanj", "Nabarangpur", "Nayagarh", "Nuapada", "Puri",
    "Rayagada", "Sambalpur", "Subarnapur", "Sundargarh",
}


# ── Odisha Airports ───────────────────────────────────────────────────────────
# 5 major airports in Odisha with IATA codes and coordinates
ODISHA_AIRPORTS: List[Dict[str, Any]] = [
    {
        "name": "Biju Patnaik International Airport",
        "city": "Bhubaneswar",
        "iata": "BBI",
        "lat": 20.2444,
        "lon": 85.8178,
        "district": "Khordha",
    },
    {
        "name": "Veer Surendra Sai Airport",
        "city": "Sambalpur (Jharsuguda)",
        "iata": "JRG",
        "lat": 21.9135,
        "lon": 84.0504,
        "district": "Jharsuguda",
    },
    {
        "name": "Jeypore Airport",
        "city": "Jeypore",
        "iata": "PYB",
        "lat": 18.8800,
        "lon": 82.5520,
        "district": "Koraput",
    },
    {
        "name": "Utkela Airport",
        "city": "Kalahandi",
        "iata": "IXL",
        "lat": 20.0990,
        "lon": 83.1840,
        "district": "Kalahandi",
    },
    {
        "name": "Rourkela Airport",
        "city": "Rourkela",
        "iata": "RRK",
        "lat": 22.1117,
        "lon": 84.8146,
        "district": "Sundargarh",
    },
]


# ── In-memory route cache ────────────────────────────────────────────────────
_GEO_CACHE: Dict[str, Tuple[dict, float]] = {}   # key → (result, timestamp)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast Haversine distance (km). Used for bulk filtering/sorting only."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


def travel_time_str(mins: float) -> str:
    """Convert minutes to human-readable string."""
    if mins < 60:
        return f"{int(mins)} min"
    return f"{mins / 60:.1f} hrs"


def nearest_odisha_airport(src_lat: float, src_lon: float) -> Dict[str, Any]:
    """
    Find the nearest Odisha airport to a source location (by haversine).
    Returns full airport dict.
    """
    best = min(
        ODISHA_AIRPORTS,
        key=lambda a: haversine_km(src_lat, src_lon, a["lat"], a["lon"]),
    )
    return best


async def geo_road_km(
    lat1: float, lon1: float, lat2: float, lon2: float, mode: str = "Road"
) -> dict:
    """
    Async road distance using real routing APIs.
    Priority:
      1. OSRM public API (free, no key, OpenStreetMap data — same engine as many apps)
      2. Geoapify Routing API (needs GEOAPIFY_API_KEY)
      3. Haversine × road_factor (final fallback)

    For Flight mode this is still called for ground legs (airport→destination).

    Returns: {"km": float, "mins": int}
    """
    cache_key = f"{lat1:.4f},{lon1:.4f},{lat2:.4f},{lon2:.4f},{mode}"
    now = time.monotonic()

    if cache_key in _GEO_CACHE:
        result, ts = _GEO_CACHE[cache_key]
        if now - ts < settings.GEO_CACHE_TTL_SECONDS:
            return result

    # OSRM — free, no API key, OpenStreetMap-based (same data Google Maps uses)
    result = await _call_osrm(lat1, lon1, lat2, lon2)
    if result:
        _GEO_CACHE[cache_key] = (result, now)
        return result

    # Geoapify fallback
    api_key = settings.GEOAPIFY_API_KEY
    if api_key and not api_key.startswith("xxx"):
        result = await _call_geoapify(lat1, lon1, lat2, lon2, mode, api_key)
        if result:
            _GEO_CACHE[cache_key] = (result, now)
            return result

    # Final fallback: haversine × road factor
    result = _haversine_fallback(lat1, lon1, lat2, lon2, mode)
    _GEO_CACHE[cache_key] = (result, now)
    return result


async def _call_osrm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Optional[dict]:
    """
    Call OSRM public demo server for real road routing.
    OSRM uses OpenStreetMap data — the same underlying data as many real map apps.
    Returns {"km": float, "mins": int} or None on failure.
    """
    # OSRM expects lon,lat order
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
        f"?overview=false&annotations=false"
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            data = r.json()
            routes = data.get("routes", [])
            if routes:
                dist_m = routes[0].get("distance", 0)
                time_s = routes[0].get("duration", 0)
                if dist_m > 0:
                    km = round(dist_m / 1000, 1)
                    mins = round(time_s / 60)
                    logger.debug(f"[OSRM] {lat1:.3f},{lon1:.3f}→{lat2:.3f},{lon2:.3f}: {km} km, {mins} min")
                    return {"km": km, "mins": mins}
        logger.warning(f"[OSRM] HTTP {r.status_code} or no routes")
    except Exception as e:
        logger.warning(f"[OSRM] error: {e}")
    return None


async def _call_geoapify(
    lat1: float, lon1: float, lat2: float, lon2: float, mode: str, api_key: str
) -> Optional[dict]:
    """Call Geoapify routing API asynchronously (secondary fallback)."""
    geo_mode = {"Road": "drive", "Train": "drive", "Flight": "drive"}.get(mode, "drive")
    url = (
        f"https://api.geoapify.com/v1/routing"
        f"?waypoints={round(lon1,6)},{round(lat1,6)}|{round(lon2,6)},{round(lat2,6)}"
        f"&mode={geo_mode}"
        f"&apiKey={api_key}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            data = r.json()
            feats = data.get("features", [])
            if feats:
                props = feats[0].get("properties", {})
                dist_m = props.get("distance", 0)
                time_s = props.get("time", 0)
                if dist_m > 0:
                    return {"km": round(dist_m / 1000, 1), "mins": round(time_s / 60)}
        logger.warning(f"[Geoapify] HTTP {r.status_code}")
    except Exception as e:
        logger.warning(f"[Geoapify] error: {e} — using haversine fallback")
    return None


def _haversine_fallback(lat1: float, lon1: float, lat2: float, lon2: float, mode: str) -> dict:
    hav = haversine_km(lat1, lon1, lat2, lon2)
    road_km = round(hav * settings.GEO_ROAD_FACTOR, 1)
    speed = {"Road": 45, "Train": 60, "Flight": 600}.get(mode, 45)
    mins = round((road_km / speed) * 60)
    return {"km": road_km, "mins": mins}


# ── District helpers ─────────────────────────────────────────────────────────

def city_coords(name: str, loader: DataLoader) -> Optional[Tuple[float, float]]:
    """Resolve a city name to (lat, lon). Works for both Odisha and non-Odisha cities."""
    key = name.lower().strip()
    if key in CITY_COORDS:
        return CITY_COORDS[key]
    for p in loader.places:
        pname = str(p.get("place_name", "")).lower()
        dist  = str(p.get("district", "")).lower()
        if key in pname or key in dist:
            try:
                return (float(p["latitude"]), float(p["longitude"]))
            except Exception:
                pass
    return None


def is_odisha_city(name: str, loader: DataLoader) -> bool:
    """Return True if the city name resolves to an Odisha district or place."""
    key = name.lower().strip()
    if key in _CITY_TO_DISTRICT:
        return True
    if name.strip().title() in ODISHA_DISTRICTS:
        return True
    for p in loader.places:
        pname = str(p.get("place_name", "")).lower().strip()
        dist  = str(p.get("district", "")).lower().strip()
        if pname == key or dist == key:
            return True
    return False


def nearest_odisha_entry_district(lat: float, lon: float) -> Tuple[str, float, float]:
    """
    Find the nearest Odisha district HQ to an external (non-Odisha) city.
    Returns (district_name, hq_lat, hq_lon).
    """
    district_hqs = {
        d: CITY_COORDS.get(d.lower(), None)
        for d in ODISHA_DISTRICTS
    }
    best_dist = float("inf")
    best_name = "Ganjam"
    best_lat, best_lon = 19.3167, 84.1000

    for dname, coords in district_hqs.items():
        if coords is None:
            continue
        d_lat, d_lon = coords
        km = haversine_km(lat, lon, d_lat, d_lon)
        if km < best_dist:
            best_dist = km
            best_name = dname
            best_lat, best_lon = d_lat, d_lon

    return best_name, best_lat, best_lon


_CITY_TO_DISTRICT = {
    "bhubaneswar":  "Khordha",
    "rourkela":     "Sundargarh",
    "berhampur":    "Ganjam",
    "brahmapur":    "Ganjam",
    "baripada":     "Mayurbhanj",
    "jeypore":      "Koraput",
    "konark":       "Puri",
    "puri":         "Puri",
    "cuttack":      "Cuttack",
    "sambalpur":    "Sambalpur",
    "koraput":      "Koraput",
    "balasore":     "Balasore",
    "baleswar":     "Balasore",
    "keonjhar":     "Keonjhar",
    "kendujhar":    "Keonjhar",
    "jharsuguda":   "Jharsuguda",
    "angul":        "Angul",
    "dhenkanal":    "Dhenkanal",
    "bolangir":     "Balangir",
    "balangir":     "Balangir",
    "phulbani":     "Kandhamal",
    "bhawanipatna": "Kalahandi",
    "sonepur":      "Subarnapur",
    "paralakhemundi":"Gajapati",
    "chatrapur":    "Ganjam",
}


def get_place_district(city_name: str, loader: DataLoader) -> str:
    key = city_name.lower().strip()
    if key in _CITY_TO_DISTRICT:
        return _CITY_TO_DISTRICT[key]
    for p in loader.places:
        pname = str(p.get("place_name", "")).lower().strip()
        dist  = str(p.get("district", "")).strip()
        if pname == key or str(p.get("district", "")).lower().strip() == key:
            return dist
    return city_name.strip().title()


def get_route_districts(src_dist: str, dst_dist: str) -> List[str]:
    if src_dist == dst_dist:
        return []
    from collections import deque
    visited = {src_dist}
    queue: deque = deque([[src_dist]])
    while queue:
        path = queue.popleft()
        for neighbor in DISTRICT_ADJACENT.get(path[-1], []):
            if neighbor == dst_dist:
                return path[1:]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return []


async def geo_route_sequence(
    places: List[Dict[str, Any]],
    src_lat: float,
    src_lon: float,
    dst_lat: float,
    dst_lon: float,
    mode: str = "Road",
) -> List[Dict[str, Any]]:
    """
    Order places geographically using haversine for sorting,
    then compute REAL road distances between consecutive stops via OSRM.

    NOTE: Nearest-neighbour removed — places are now sorted by their
    haversine distance along the src→dst corridor, which avoids
    backtracking without the NN greedy artefacts.
    """
    if not places:
        return []

    # Sort places by their position along the src→dst axis
    # (project each place onto the great-circle and sort by that fraction)
    def corridor_position(p: Dict) -> float:
        try:
            plat, plon = float(p["latitude"]), float(p["longitude"])
            d_from_src = haversine_km(src_lat, src_lon, plat, plon)
            d_from_dst = haversine_km(dst_lat, dst_lon, plat, plon)
            total = d_from_src + d_from_dst
            return d_from_src / total if total > 0 else 0.5
        except Exception:
            return 0.5

    ordered = sorted(places, key=corridor_position)

    # Compute REAL road distances between consecutive stops
    result: List[Dict[str, Any]] = []
    prev_lat, prev_lon = src_lat, src_lon
    prev_name = "Source"

    for p in ordered:
        try:
            plat, plon = float(p["latitude"]), float(p["longitude"])
        except Exception:
            result.append({**p, "distance_from_prev": 0, "time_from_prev": 0, "prev_name": prev_name})
            continue
        road = await geo_road_km(prev_lat, prev_lon, plat, plon, mode)
        result.append({
            **p,
            "distance_from_prev": road["km"],
            "time_from_prev": road["mins"],
            "prev_name": prev_name,
        })
        prev_lat, prev_lon = plat, plon
        prev_name = str(p.get("place_name", ""))

    # Last place → destination
    if result:
        try:
            last = result[-1]
            last_road = await geo_road_km(
                float(last["latitude"]), float(last["longitude"]), dst_lat, dst_lon, mode
            )
            result[-1]["dist_to_dest"] = last_road["km"]
            result[-1]["time_to_dest"] = last_road["mins"]
        except Exception:
            pass

    return result
