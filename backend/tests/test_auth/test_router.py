from app.config import settings
from app.core.rate_limit import limiter
from app.main import app


def test_auth_routes_are_registered(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/auth/me" in paths
    assert "/api/v1/auth/onboarding" in paths
    assert "/api/v1/auth/invites/accept" in paths


def test_legacy_password_routes_are_gone(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/auth/register" not in paths
    assert "/api/v1/auth/login" not in paths
    assert "/api/v1/auth/refresh" not in paths
    assert "/api/v1/auth/logout" not in paths


def test_rate_limiter_is_configured():
    assert app.state.limiter is limiter
    assert settings.rate_limit_default == "100/minute"
