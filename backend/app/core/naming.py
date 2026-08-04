from __future__ import annotations

"""
SQLAlchemy naming convention for database constraints.
Ensures consistent constraint naming across the entire project.
"""

naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

"""
USAGE IN base.py:

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from app.core.naming import naming_convention

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)
    type_annotation_map = {...}

This ensures all auto-generated constraint names follow the convention.
"""
