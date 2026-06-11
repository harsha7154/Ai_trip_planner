"""
Application configuration — reads from environment variables / .env file.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── API Keys ────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENWEATHER_API_KEY: str = ""
    GEOAPIFY_API_KEY: str = ""

    # ── App ─────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # ── Data ────────────────────────────────────────────────────
    DATA_FILE: str = "data/places.xlsx"

    # ── LLM ─────────────────────────────────────────────────────
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_MODEL: str = "models/gemini-2.5-flash-lite"
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 0.3

    # ── Geo ─────────────────────────────────────────────────────
    GEO_ROAD_FACTOR: float = 1.3          # Haversine → road distance multiplier
    GEO_FALLBACK_FACTOR: float = 1.17     # secondary fallback factor
    GEO_CACHE_TTL_SECONDS: int = 3600     # in-memory cache TTL

    # ── Monitoring ───────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


settings = Settings()
