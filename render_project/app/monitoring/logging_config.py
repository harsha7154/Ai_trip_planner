"""
Loguru logging configuration.
- Console: coloured, human-readable
- File: JSON-structured (for log aggregators like Loki, Datadog)
- Rotation: 10 MB, 7 days retention
"""
import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings


def setup_logging() -> None:
    """Configure Loguru for the application."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # ── Console handler ────────────────────────────────────────────────────────
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # ── File handler (JSON for log aggregators) ────────────────────────────────
    logger.add(
        log_dir / "app.log",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} — {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        serialize=False,   # Set True for pure JSON logs (Loki/Grafana)
        backtrace=True,
        diagnose=False,    # Disable in production to avoid leaking vars
    )

    # ── Error-only file ────────────────────────────────────────────────────────
    logger.add(
        log_dir / "errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} — {message}",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
    )

    logger.info(f"Logging configured | env={settings.APP_ENV} | level={settings.LOG_LEVEL}")
