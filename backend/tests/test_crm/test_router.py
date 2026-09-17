def test_crm_routes_are_registered(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/crm/lead-sources" in paths
    assert "/api/v1/crm/leads" in paths
    assert "/api/v1/crm/leads/{lead_id}" in paths
    assert "/api/v1/crm/leads/{lead_id}/convert" in paths
    assert "/api/v1/crm/leads/{lead_id}/lost" in paths
    assert "/api/v1/crm/leads/{lead_id}/follow-ups" in paths
    assert "/api/v1/crm/follow-ups/{follow_up_id}/complete" in paths


def test_crm_lead_endpoints_support_expected_methods(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/api/v1/crm/leads"]) >= {"get", "post"}
    assert set(paths["/api/v1/crm/leads/{lead_id}"]) >= {"get", "patch"}
