def test_rbac_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    assert "/api/v1/rbac/permissions" in schema["paths"]
    assert "/api/v1/rbac/roles" in schema["paths"]
    assert "/api/v1/rbac/users/{user_id}/roles" in schema["paths"]
