from __future__ import annotations

import logging

from app.config import settings

_configured = False


def configure_logging() -> None:
    """Configure application logging once, at app startup."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _configured = True
