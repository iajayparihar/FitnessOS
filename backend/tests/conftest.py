import pytest

from app.main import app


class OpenAPIResponse:
    """Minimal response helper for OpenAPI route registration tests."""

    def json(self):
        return app.openapi()


class OpenAPIClient:
    """Minimal client helper for tests that only read OpenAPI."""

    def get(self, path: str):
        if path != "/openapi.json":
            raise ValueError(f"Unsupported test path: {path}")
        return OpenAPIResponse()


@pytest.fixture
def client():
    return OpenAPIClient()
