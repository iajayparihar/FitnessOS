"""Local-user provisioning from a verified Clerk identity."""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.integrations.clerk.authentication import (
    ClerkIdentity,
    authenticate_clerk_session,
    get_user_by_clerk_id,
    identity_from_claims,
    provision_user_from_identity,
)
from app.integrations.clerk.exceptions import (
    ClerkAuthenticationError,
    ClerkIdentityConflict,
)
from app.modules.auth.exceptions import InactiveUser
from app.modules.auth.models import AuthProvider, User, UserAuthMethod


def _identity(**overrides) -> ClerkIdentity:
    values = {
        "clerk_user_id": "user_provision_1",
        "email": "owner@example.com",
        "email_verified": True,
        "session_id": "sess_1",
    }
    values.update(overrides)
    return ClerkIdentity(**values)


def test_identity_requires_a_subject():
    with pytest.raises(ClerkAuthenticationError):
        identity_from_claims({"azp": "http://localhost:3000"})


def test_identity_falls_back_to_a_stable_placeholder_email():
    identity = identity_from_claims({"sub": "user_noemail"})

    assert identity.email is None
    assert identity.local_email == "clerk-user_noemail@local.invalid"


async def test_first_sign_in_creates_a_local_user(db_session):
    user = await provision_user_from_identity(db_session, identity=_identity())

    assert user.clerk_user_id == "user_provision_1"
    assert user.email == "owner@example.com"
    assert user.is_active is True
    assert user.organization_id is None, "tenant is created by onboarding, not sign-in"


async def test_provisioning_is_idempotent(db_session):
    first = await provision_user_from_identity(db_session, identity=_identity())
    second = await provision_user_from_identity(db_session, identity=_identity())

    assert first.id == second.id

    result = await db_session.execute(select(func.count()).select_from(User))
    assert result.scalar_one() == 1


async def test_provisioning_binds_exactly_one_clerk_auth_method(db_session):
    await provision_user_from_identity(db_session, identity=_identity())
    await provision_user_from_identity(db_session, identity=_identity())

    result = await db_session.execute(
        select(UserAuthMethod).where(
            UserAuthMethod.provider == AuthProvider.CLERK,
        )
    )
    methods = list(result.scalars())
    assert len(methods) == 1
    assert methods[0].provider_uid == "user_provision_1"


async def test_distinct_clerk_identities_get_distinct_users(db_session):
    first = await provision_user_from_identity(
        db_session, identity=_identity(clerk_user_id="user_a", email="a@example.com")
    )
    second = await provision_user_from_identity(
        db_session, identity=_identity(clerk_user_id="user_b", email="b@example.com")
    )

    assert first.id != second.id


async def test_duplicate_clerk_id_cannot_be_inserted(db_session):
    """The partial unique index is what makes concurrent provisioning safe."""
    await provision_user_from_identity(db_session, identity=_identity())

    db_session.add(
        User(
            clerk_user_id="user_provision_1",
            email="duplicate@example.com",
            is_active=True,
        )
    )
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()


async def test_email_linking_is_off_by_default(db_session):
    """A Clerk sign-up must not silently claim a pre-existing account by email."""
    legacy = User(email="legacy@example.com", is_active=True)
    db_session.add(legacy)
    await db_session.commit()

    with pytest.raises(ClerkIdentityConflict):
        await provision_user_from_identity(
            db_session,
            identity=_identity(clerk_user_id="user_new", email="legacy@example.com"),
        )

    await db_session.rollback()
    await db_session.refresh(legacy)
    assert legacy.clerk_user_id is None, "the legacy account must stay unlinked"


async def test_email_linking_migrates_a_legacy_user_when_enabled(
    db_session, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "clerk_link_existing_users_by_email", True)
    legacy = User(email="legacy@example.com", is_active=True)
    db_session.add(legacy)
    await db_session.commit()
    legacy_id = legacy.id

    linked = await provision_user_from_identity(
        db_session,
        identity=_identity(clerk_user_id="user_new", email="legacy@example.com"),
    )

    assert linked.id == legacy_id, "the FitnessOS UUID must survive migration"
    assert linked.clerk_user_id == "user_new"


async def test_email_linking_refuses_unverified_emails(db_session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "clerk_link_existing_users_by_email", True)
    legacy = User(email="legacy@example.com", is_active=True)
    db_session.add(legacy)
    await db_session.commit()

    with pytest.raises(ClerkIdentityConflict):
        await provision_user_from_identity(
            db_session,
            identity=_identity(
                clerk_user_id="user_new",
                email="legacy@example.com",
                email_verified=False,
            ),
        )

    await db_session.rollback()
    await db_session.refresh(legacy)
    assert legacy.clerk_user_id is None


async def test_email_linking_never_steals_an_already_linked_account(
    db_session, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "clerk_link_existing_users_by_email", True)
    owner = User(email="shared@example.com", clerk_user_id="user_owner", is_active=True)
    db_session.add(owner)
    await db_session.commit()

    with pytest.raises(ClerkIdentityConflict):
        await provision_user_from_identity(
            db_session,
            identity=_identity(
                clerk_user_id="user_attacker", email="shared@example.com"
            ),
        )

    await db_session.rollback()
    await db_session.refresh(owner)
    assert owner.clerk_user_id == "user_owner", "the owner must keep their identity"


async def test_inactive_user_is_rejected(db_session, clerk_settings, make_clerk_token):
    user = await provision_user_from_identity(db_session, identity=_identity())
    user.is_active = False
    await db_session.commit()

    token = make_clerk_token(subject="user_provision_1")
    with pytest.raises(InactiveUser):
        await authenticate_clerk_session(db_session, token=token)


async def test_authenticate_resolves_the_existing_local_user(
    db_session, clerk_settings, make_clerk_token
):
    created = await provision_user_from_identity(db_session, identity=_identity())

    token = make_clerk_token(subject="user_provision_1")
    resolved = await authenticate_clerk_session(db_session, token=token)

    assert resolved.id == created.id


async def test_soft_deleted_users_are_not_resolved(db_session):
    user = await provision_user_from_identity(db_session, identity=_identity())
    user.deleted_at = datetime.now(UTC)
    await db_session.commit()

    assert (
        await get_user_by_clerk_id(db_session, clerk_user_id="user_provision_1") is None
    )


async def test_concurrent_first_sign_ins_converge_on_one_user(db_engine):
    """Two simultaneous first requests must not create two local users."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def provision():
        async with session_maker() as session:
            return await provision_user_from_identity(
                session, identity=_identity(clerk_user_id="user_race")
            )

    results = await asyncio.gather(provision(), provision(), return_exceptions=True)
    users = [r for r in results if isinstance(r, User)]
    assert users, f"no user provisioned: {results}"
    assert len({user.id for user in users}) == 1

    async with session_maker() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(User.clerk_user_id == "user_race")
        )
        assert result.scalar_one() == 1
        await session.execute(
            User.__table__.delete().where(User.clerk_user_id == "user_race")
        )
        await session.commit()
