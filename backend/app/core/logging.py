from __future__ import annotations

import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_log_level(debug: bool | None = None) -> int:
    """Resolve the effective log level from environment and app settings."""
    if debug is None:
        debug = os.getenv("APP_DEBUG", "").lower() in {"1", "true", "yes", "on"}

    configured = os.getenv("LOG_LEVEL", "").strip()
    if configured:
        level = getattr(logging, configured.upper(), None)
        if isinstance(level, int):
            return level

    return logging.DEBUG if debug else logging.INFO


def configure_logging(debug: bool | None = None) -> logging.Logger:
    """Configure application logging for console and rotating file output."""
    debug_enabled = debug if debug is not None else os.getenv("APP_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    log_level = _resolve_log_level(debug_enabled)
    log_directory = Path(os.getenv("LOG_DIR", "logs"))
    log_directory.mkdir(parents=True, exist_ok=True)
    log_file = log_directory / "fitness_business_os.log"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": DEFAULT_LOG_FORMAT,
                "datefmt": DEFAULT_DATE_FORMAT,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG" if debug_enabled else "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_file),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {"handlers": ["console", "file"], "level": log_level, "propagate": False},
            "uvicorn.error": {"handlers": ["console", "file"], "level": log_level, "propagate": False},
            "uvicorn.access": {"handlers": ["console"], "level": log_level, "propagate": False},
            "sqlalchemy.engine": {"handlers": ["console", "file"], "level": logging.WARNING, "propagate": False},
            "sqlalchemy.pool": {"handlers": ["console", "file"], "level": logging.WARNING, "propagate": False},
        },
        "root": {"handlers": ["console", "file"], "level": log_level},
    }

    logging.config.dictConfig(logging_config)
    logging.captureWarnings(True)

    logger = logging.getLogger("fitness_business_os")
    logger.setLevel(log_level)
    logger.info("Application logging configured (level=%s, file=%s)", logging.getLevelName(log_level), log_file)
    return logger


logger = logging.getLogger("fitness_business_os")
