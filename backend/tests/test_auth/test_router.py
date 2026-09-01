def test_auth_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/auth/logout" in schema["paths"]
    assert "/api/v1/auth/forgot-password" in schema["paths"]
    assert "/api/v1/auth/reset-password" in schema["paths"]
    assert "/api/v1/auth/verify-email" in schema["paths"]
    assert "/api/v1/auth/resend-verification" in schema["paths"]
    assert "/api/v1/auth/me" in schema["paths"]
