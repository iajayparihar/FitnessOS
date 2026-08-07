from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator, DateTime

from app.core.naming import naming_convention


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.x declarative base with type annotation mapping.
    All models inherit from this base.
    """

    metadata = MetaData(naming_convention=naming_convention)

    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict: JSONB,
        list: ARRAY(str),
    }


# Ensure all SQLAlchemy models are imported and registered with Base.metadata
import app.db.models  # noqa: F401
