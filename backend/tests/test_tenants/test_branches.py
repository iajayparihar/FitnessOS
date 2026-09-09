"""Branch management and the one-main-branch invariant."""

import uuid

import pytest
from sqlalchemy import select

from app.modules.tenants.models import OrganizationBranch
from tests.test_tenants.test_organizations import auth_header, create_org


async def _org_and_token(api_client, make_clerk_token, subject, name):
    token = make_clerk_token(subject=subject)
    data = await create_org(api_client, token, name)
    return token, data["organization"]["id"], data["main_branch"]["id"]


async def test_main_branch_is_created_with_the_organization(
    api_client, make_clerk_token
):
    token, organization_id, main_branch_id = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    response = await api_client.get(
        f"/api/v1/organizations/{organization_id}/branches", headers=auth_header(token)
    )

    assert response.status_code == 200
    branches = response.json()["data"]
    assert len(branches) == 1
    assert branches[0]["id"] == main_branch_id
    assert branches[0]["is_main"] is True


async def test_branch_can_be_created_read_updated_and_deleted(
    api_client, make_clerk_token
):
    token, organization_id, _ = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    created = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json={"name": "Andheri West", "code": "AW", "phone": "+91 90000 00000"},
        headers=auth_header(token),
    )
    assert created.status_code == 201, created.text
    branch_id = created.json()["data"]["id"]
    assert created.json()["data"]["organization_id"] == organization_id

    fetched = await api_client.get(
        f"/api/v1/organizations/{organization_id}/branches/{branch_id}",
        headers=auth_header(token),
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["code"] == "AW"

    updated = await api_client.patch(
        f"/api/v1/organizations/{organization_id}/branches/{branch_id}",
        json={"name": "Andheri East"},
        headers=auth_header(token),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Andheri East"

    deleted = await api_client.delete(
        f"/api/v1/organizations/{organization_id}/branches/{branch_id}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 204

    gone = await api_client.get(
        f"/api/v1/organizations/{organization_id}/branches/{branch_id}",
        headers=auth_header(token),
    )
    assert gone.status_code == 404


async def test_branch_delete_is_a_soft_delete(api_client, make_clerk_token, db_session):
    token, organization_id, _ = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )
    created = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json={"name": "Bandra"},
        headers=auth_header(token),
    )
    branch_id = uuid.UUID(created.json()["data"]["id"])

    await api_client.delete(
        f"/api/v1/organizations/{organization_id}/branches/{branch_id}",
        headers=auth_header(token),
    )

    result = await db_session.execute(
        select(OrganizationBranch).where(OrganizationBranch.id == branch_id)
    )
    branch = result.scalar_one()
    assert branch.deleted_at is not None
    assert branch.is_active is False


async def test_the_main_branch_cannot_be_deleted(api_client, make_clerk_token):
    token, organization_id, main_branch_id = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    response = await api_client.delete(
        f"/api/v1/organizations/{organization_id}/branches/{main_branch_id}",
        headers=auth_header(token),
    )

    assert response.status_code == 409


async def test_the_main_flag_cannot_simply_be_cleared(api_client, make_clerk_token):
    token, organization_id, main_branch_id = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    response = await api_client.patch(
        f"/api/v1/organizations/{organization_id}/branches/{main_branch_id}",
        json={"is_main": False},
        headers=auth_header(token),
    )

    assert response.status_code == 409


async def test_promoting_a_branch_demotes_the_previous_main(
    api_client, make_clerk_token
):
    token, organization_id, main_branch_id = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )
    created = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json={"name": "Powai"},
        headers=auth_header(token),
    )
    new_branch_id = created.json()["data"]["id"]

    promoted = await api_client.patch(
        f"/api/v1/organizations/{organization_id}/branches/{new_branch_id}",
        json={"is_main": True},
        headers=auth_header(token),
    )
    assert promoted.status_code == 200

    branches = await api_client.get(
        f"/api/v1/organizations/{organization_id}/branches", headers=auth_header(token)
    )
    mains = [b["id"] for b in branches.json()["data"] if b["is_main"]]
    assert mains == [new_branch_id]


async def test_creating_a_main_branch_demotes_the_previous_one(
    api_client, make_clerk_token
):
    token, organization_id, main_branch_id = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    created = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json={"name": "New HQ", "is_main": True},
        headers=auth_header(token),
    )
    assert created.status_code == 201

    branches = await api_client.get(
        f"/api/v1/organizations/{organization_id}/branches", headers=auth_header(token)
    )
    mains = [b["id"] for b in branches.json()["data"] if b["is_main"]]
    assert len(mains) == 1
    assert mains[0] != main_branch_id


async def test_one_main_branch_is_enforced_by_the_database(
    api_client, make_clerk_token, db_session
):
    """The partial unique index is what makes the invariant race-proof."""
    _, organization_id, _ = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )

    db_session.add(
        OrganizationBranch(
            organization_id=uuid.UUID(organization_id),
            name="Rogue Main",
            is_main=True,
        )
    )
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()


async def test_duplicate_branch_names_are_rejected(api_client, make_clerk_token):
    token, organization_id, _ = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Branchy Gym"
    )
    body = {"name": "Colaba"}

    first = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json=body,
        headers=auth_header(token),
    )
    second = await api_client.post(
        f"/api/v1/organizations/{organization_id}/branches",
        json=body,
        headers=auth_header(token),
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_the_same_branch_name_is_free_in_another_organization(
    api_client, make_clerk_token
):
    token_a, org_a, _ = await _org_and_token(
        api_client, make_clerk_token, "user_a", "Gym A"
    )
    token_b, org_b, _ = await _org_and_token(
        api_client, make_clerk_token, "user_b", "Gym B"
    )

    first = await api_client.post(
        f"/api/v1/organizations/{org_a}/branches",
        json={"name": "Colaba"},
        headers=auth_header(token_a),
    )
    second = await api_client.post(
        f"/api/v1/organizations/{org_b}/branches",
        json={"name": "Colaba"},
        headers=auth_header(token_b),
    )

    assert first.status_code == 201
    assert second.status_code == 201


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


async def test_default_settings_are_readable_and_updatable(
    api_client, make_clerk_token
):
    token, organization_id, _ = await _org_and_token(
        api_client, make_clerk_token, "user_owner", "Configured Gym"
    )

    listing = await api_client.get(
        f"/api/v1/organizations/{organization_id}/settings", headers=auth_header(token)
    )
    assert listing.status_code == 200
    assert {row["key"] for row in listing.json()["data"]} == {
        "locale",
        "business_hours",
        "notifications",
    }

    updated = await api_client.put(
        f"/api/v1/organizations/{organization_id}/settings",
        json={"key": "notifications", "value": {"email_enabled": False}},
        headers=auth_header(token),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["value"] == {"email_enabled": False}

    count = await api_client.get(
        f"/api/v1/organizations/{organization_id}/settings", headers=auth_header(token)
    )
    assert len(count.json()["data"]) == 3, "upsert must replace, not duplicate"
