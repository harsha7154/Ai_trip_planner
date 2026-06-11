"""
Odisha AI Trip Planner — Production FastAPI Application
Entry point: uvicorn app.main:app
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
import os
from pathlib import Path

from app.api.routes import router
from app.data.loader import DataLoader
from app.monitoring.metrics import setup_metrics
from app.monitoring.logging_config import setup_logging
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — load data once at startup."""
    setup_logging()
    logger.info("🚀 Starting Odisha AI Trip Planner...")

    loader = DataLoader()
    loader.load()
    app.state.data_loader = loader
    logger.info(f"✅ Dataset loaded: {len(loader.places)} places")

    setup_metrics(app)

    yield

    logger.info("🛑 Shutting down...")


app = FastAPI(
    title="Odisha AI Trip Planner",
    description="AI-powered trip planning API for Odisha tourism",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# ── Serve frontend static files ──────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/ui", tags=["Frontend"])
    async def serve_frontend():
        """Serve the frontend HTML UI."""
        return FileResponse(str(FRONTEND_DIR / "index.html"))


# ── Health & root ────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Odisha AI Trip Planner",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "ui": "/ui",
    }


@app.get("/health", tags=["Health"])
async def health():
    loader = getattr(app.state, "data_loader", None)
    return {
        "status": "healthy",
        "places_loaded": len(loader.places) if loader else 0,
        "data_source": "Excel",
    }
