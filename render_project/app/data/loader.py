"""
DataLoader — loads the Odisha places Excel file once at startup.
All services receive a reference to the shared DataLoader instance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from loguru import logger

from app.core.config import settings
from app.core.exceptions import DataNotLoadedError


# Column rename map — Excel header → internal snake_case key
COLUMN_RENAME: Dict[str, str] = {
    "Place Name":                "place_name",
    "District":                  "district",
    "Region (N/S/C/W)":          "region",
    "Category":                  "category",
    "Importance":                "importance",
    "Latitude":                  "latitude",
    "Longitude":                 "longitude",
    "Nearby Places":             "nearby_places",
    "Time to Cover (Hours)":     "cover_hours",
    "Key Attractions":           "key_attractions",
    "Entry Ticket":              "entry_ticket",
    "Google Map Link":           "map_link",
    "Distance & Route Info":     "route_info",
    "Place Images (URLs)":       "image_urls",
    "OTDC Stay / Panthanivas":   "otdc_stay",
    "Food Speciality (Must Try)":"food_speciality",
    "Best Time to Visit":        "best_time",
    "Activities & Budget":       "activities_budget",
}


class DataLoader:
    """
    Singleton-style data loader.
    Call .load() once at app startup; then access .places and .df everywhere.
    """

    def __init__(self) -> None:
        self._places: List[Dict[str, Any]] = []
        self._df: Optional[pd.DataFrame] = None
        self._loaded: bool = False

    # ── Public API ───────────────────────────────────────────────────────────

    def load(self, filepath: Optional[str] = None) -> None:
        """Load and normalise the Excel file. Safe to call multiple times."""
        path = Path(filepath or settings.DATA_FILE)
        if not path.exists():
            logger.warning(f"Data file not found at {path}. PLACES will be empty.")
            self._places = []
            self._df = pd.DataFrame()
            self._loaded = True
            return

        logger.info(f"Loading dataset from {path}...")
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={k: v for k, v in COLUMN_RENAME.items() if k in df.columns})

        # Coerce numerics
        df["latitude"]    = pd.to_numeric(df.get("latitude",    pd.Series(dtype=float)), errors="coerce")
        df["longitude"]   = pd.to_numeric(df.get("longitude",   pd.Series(dtype=float)), errors="coerce")
        df["cover_hours"] = pd.to_numeric(df.get("cover_hours", pd.Series(dtype=float)), errors="coerce").fillna(2.0)

        df = df.dropna(subset=["latitude", "longitude"])

        self._df = df
        self._places = df.to_dict("records")
        self._loaded = True

        logger.info(f"✅ Loaded {len(self._places)} places")
        logger.info(f"   Districts  : {sorted(set(str(p.get('district','')) for p in self._places))[:10]}...")
        logger.info(f"   Categories : {sorted(set(str(p.get('category','')) for p in self._places))}")

    @property
    def places(self) -> List[Dict[str, Any]]:
        if not self._loaded:
            raise DataNotLoadedError("DataLoader.load() has not been called yet.")
        return self._places

    @property
    def df(self) -> pd.DataFrame:
        if not self._loaded:
            raise DataNotLoadedError("DataLoader.load() has not been called yet.")
        return self._df  # type: ignore[return-value]

    def is_loaded(self) -> bool:
        return self._loaded and len(self._places) > 0

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_districts(self) -> List[str]:
        return sorted({str(p.get("district", "")).strip() for p in self._places if p.get("district")})

    def get_categories(self) -> List[str]:
        return sorted({str(p.get("category", "")).strip() for p in self._places if p.get("category")})

    def parse_image_urls(self, raw: Any, max_imgs: int = 3) -> List[str]:
        """Parse image URLs from various raw formats stored in Excel."""
        raw = str(raw).strip()
        if not raw or raw == "nan":
            return []

        urls: List[str] = []
        if raw.startswith("["):
            try:
                urls = json.loads(raw)
            except Exception:
                pass

        if not urls and "|" in raw:
            urls = [u.strip() for u in raw.split("|")]
        if not urls:
            urls = [u.strip() for u in raw.split(",")]

        cleaned = []
        for u in urls:
            u = u.strip().strip("\"'[]").strip()
            if u.startswith("http"):
                cleaned.append(u)

        return cleaned[:max_imgs]

    def get_images(self, place_name: str, max_imgs: int = 3) -> List[str]:
        """Return parsed image URLs for a given place name."""
        for p in self._places:
            if str(p.get("place_name", "")).lower() == place_name.lower():
                return self.parse_image_urls(p.get("image_urls", ""), max_imgs)
        return []
