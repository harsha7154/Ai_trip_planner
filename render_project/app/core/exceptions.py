"""Custom application exceptions."""


class TripPlannerError(Exception):
    """Base exception for trip planner."""


class DataNotLoadedError(TripPlannerError):
    """Raised when PLACES dataset is not loaded."""


class InvalidLocationError(TripPlannerError):
    """Raised when source/destination can't be resolved to coordinates."""


class LLMError(TripPlannerError):
    """Raised when both Groq and Gemini fail."""


class GeoAPIError(TripPlannerError):
    """Raised when Geoapify fails and no fallback is possible."""


class WeatherAPIError(TripPlannerError):
    """Non-fatal — weather data is optional."""
