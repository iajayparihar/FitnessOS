from __future__ import annotations

import uuid

from fastapi import FastAPI, Request

REQUEST_ID_HEADER = "X-Request-ID"


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:24]}"


def register_request_id(app: FastAPI) -> None:
    """Attach a request id to every request for log/error correlation."""

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or _new_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
