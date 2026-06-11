"""
Prometheus metrics for the Trip Planner API.
Exposes /metrics endpoint for Prometheus scraping.
"""
from fastapi import FastAPI

try:
    from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ── Define metrics ─────────────────────────────────────────────────────────────

if PROMETHEUS_AVAILABLE:
    TRIP_REQUESTS_TOTAL = Counter(
        "trip_requests_total",
        "Total number of trip planning requests",
        ["mode", "budget", "days"],
    )

    TRIP_DURATION_SECONDS = Histogram(
        "trip_duration_seconds",
        "Time taken to complete a trip planning request",
        buckets=[1, 2, 5, 10, 20, 30, 60],
    )

    LLM_CALLS_TOTAL = Counter(
        "llm_calls_total",
        "Total LLM API calls",
        ["provider", "status"],   # provider: groq|gemini, status: success|error
    )

    WEATHER_CALLS_TOTAL = Counter(
        "weather_calls_total",
        "Total weather API calls",
        ["status"],
    )

    GEO_CACHE_HITS = Counter(
        "geo_cache_hits_total",
        "Total Geoapify cache hits (saves API calls)",
    )

    PLACES_LOADED = Gauge(
        "places_loaded_total",
        "Total number of places loaded from Excel",
    )


def setup_metrics(app: FastAPI) -> None:
    """Mount the Prometheus /metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return

    from app.core.config import settings
    if not settings.PROMETHEUS_ENABLED:
        return

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
