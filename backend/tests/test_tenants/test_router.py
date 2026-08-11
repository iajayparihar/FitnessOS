def test_tenant_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    assert "/api/v1/tenants" in schema["paths"]
    assert "/api/v1/tenants/current" in schema["paths"]
