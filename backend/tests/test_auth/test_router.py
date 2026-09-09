def test_auth_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    # The legacy password routes stay in the schema for migration compatibility;
    # they answer 404 unless LEGACY_PASSWORD_AUTH_ENABLED is set.
    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/auth/logout" in schema["paths"]

    assert "/api/v1/auth/me" in schema["paths"]
    assert "/api/v1/auth/onboarding" in schema["paths"]
    assert "/api/v1/auth/context" in schema["paths"]


def test_legacy_password_routes_are_marked_deprecated(client):
    schema = client.get("/openapi.json").json()

    for path in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    ):
        assert schema["paths"][path]["post"]["deprecated"] is True


def test_clerk_routes_are_not_deprecated(client):
    schema = client.get("/openapi.json").json()

    assert not schema["paths"]["/api/v1/auth/me"]["get"].get("deprecated")
    assert not schema["paths"]["/api/v1/auth/onboarding"]["post"].get("deprecated")
