def test_rbac_routes_are_registered(client):
    schema = client.get("/openapi.json").json()

    assert "/api/v1/rbac/permissions" in schema["paths"]
    assert "/api/v1/rbac/roles" in schema["paths"]
    assert "/api/v1/rbac/users/{user_id}/roles" in schema["paths"]


async def test_roles_endpoint_lists_the_system_catalogue(api_client, make_clerk_token):
    """An owner must be able to discover the roles they can assign."""
    from tests.test_tenants.test_organizations import auth_header, create_org

    token = make_clerk_token(subject="user_owner")
    await create_org(api_client, token, "Catalogue Gym")

    response = await api_client.get("/api/v1/rbac/roles", headers=auth_header(token))

    assert response.status_code == 200
    by_slug = {row["slug"]: row for row in response.json()["data"]}
    assert set(by_slug) >= {
        "owner",
        "admin",
        "manager",
        "trainer",
        "staff",
        "member",
    }
    assert all(by_slug[slug]["is_system"] for slug in by_slug)
    assert by_slug["manager"]["description"]


async def test_permissions_endpoint_lists_the_full_catalogue(
    api_client, make_clerk_token
):
    from app.modules.rbac.service import ALL_PERMISSION_CODES
    from tests.test_tenants.test_organizations import auth_header, create_org

    token = make_clerk_token(subject="user_owner")
    await create_org(api_client, token, "Catalogue Gym")

    response = await api_client.get(
        "/api/v1/rbac/permissions", headers=auth_header(token)
    )

    assert response.status_code == 200
    codes = {row["code"] for row in response.json()["data"]}
    assert codes == set(ALL_PERMISSION_CODES)
