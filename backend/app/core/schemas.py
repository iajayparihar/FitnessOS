from __future__ import annotations

from pydantic import BaseModel


class PageMeta(BaseModel):
    """Pagination metadata for list responses (see ``docs/API.md``)."""

    page: int
    page_size: int
    total: int
    total_pages: int


def page_meta(*, total: int, page: int, page_size: int) -> PageMeta:
    """Build :class:`PageMeta` from a total count and the current page window."""
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return PageMeta(page=page, page_size=page_size, total=total, total_pages=total_pages)
