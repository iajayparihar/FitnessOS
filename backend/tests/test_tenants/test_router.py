ORGANIZATION_PATHS = (
    "/api/v1/organizations",
    "/api/v1/organizations/{organization_id}",
    "/api/v1/organizations/{organization_id}/switch",
    "/api/v1/organizations/{organization_id}/members",
    "/api/v1/organizations/{organization_id}/members/{user_id}",
    "/api/v1/organizations/{organization_id}/branches",
    "/api/v1/organizations/{organization_id}/branches/{branch_id}",
    "/api/v1/organizations/{organization_id}/settings",
)


def test_organization_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    for path in ORGANIZATION_PATHS:
        assert path in schema["paths"], path


def test_legacy_tenant_routes_are_preserved(client):
    """The original /tenants surface still answers, so existing clients keep working."""
    schema = client.get("/openapi.json").json()

    assert "/api/v1/tenants" in schema["paths"]
    assert "/api/v1/tenants/current" in schema["paths"]
    assert schema["paths"]["/api/v1/tenants"]["post"]["deprecated"] is True


def test_organization_endpoints_are_documented(client):
    schema = client.get("/openapi.json").json()

    for path in ORGANIZATION_PATHS:
        for operation in schema["paths"][path].values():
            assert operation.get("summary"), f"{path} is missing a summary"


def test_no_request_schema_accepts_an_organization_id(client):
    """
    The tenant is resolved server-side, so no request body may nominate one.

    A schema that accepted organization_id would invite an endpoint to trust it.
    """
    schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]

    for name in (
        "OrgCreate",
        "OrgUpdate",
        "OrgProvisionRequest",
        "BranchCreate",
        "BranchUpdate",
        "MembershipCreate",
        "MembershipUpdate",
        "SettingUpsert",
    ):
        properties = components[name].get("properties", {})
        assert "organization_id" not in properties, name
