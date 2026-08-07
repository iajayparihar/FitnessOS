from .base import Base

# Import this module to register all SQLAlchemy models automatically.
from . import models  # noqa: F401

__all__ = ["Base"]
