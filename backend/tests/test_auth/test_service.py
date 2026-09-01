import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import (
    TokenExpired,
    create_access_token,
    decode_jwt,
    encode_jwt,
    hash_password,
    verify_password,
)
from app.modules.analytics.models import AuditLog
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import AuthActionRateLimited, InvalidAuthActionToken
from app.modules.auth.models import (
    AuthActionToken,
    AuthActionTokenPurpose,
    AuthProvider,
    User,
    UserAuthMethod,
)
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.modules.auth.service import (
    hash_action_token,
    request_password_reset,
    resend_email_verification,
    reset_password,
    validate_action_token,
    verify_email,
)
from app.modules.notifications.models import Notification


class QueryResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return iter(self.value or [])


class CapturingSession:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.statements = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        return QueryResult(value)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if hasattr(value, "id") and value.id is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


def make_user(
    *,
    email_verified: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="user@example.com",
        email_verified=email_verified,
        is_active=is_active,
        is_superuser=False,
    )
    user.auth_methods = [
        UserAuthMethod(
            id=uuid.uuid4(),
            user_id=user.id,
            provider=AuthProvider.PASSWORD,
            password_hash=hash_password("old-password"),
            is_primary=True,
        )
    ]
    return user


def test_password_hash_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    token = create_access_token(
        subject=user_id,
        organization_id=organization_id,
        is_superuser=False,
        session_id=uuid.uuid4(),
    )
    payload = decode_jwt(token)

    assert payload["sub"] == str(user_id)
    assert payload["organization_id"] == str(organization_id)
    assert "sid" in payload
    assert payload["type"] == "access"


def test_decode_jwt_rejects_tampered_signature():
    token = create_access_token(
        subject=uuid.uuid4(),
        organization_id=None,
        is_superuser=False,
        session_id=uuid.uuid4(),
    )
    header, payload, signature = token.split(".")

    with pytest.raises(ValueError):
        decode_jwt(f"{header}.{payload}.{signature[:-2]}xx")


def test_decode_jwt_rejects_expired_token_with_specific_error():
    token = encode_jwt(
        {
            "sub": uuid.uuid4(),
            "sid": uuid.uuid4(),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=30),
            "exp": datetime.now(UTC) - timedelta(minutes=15),
        }
    )

    with pytest.raises(TokenExpired):
        decode_jwt(token)


def test_get_current_user_reports_expired_access_token():
    token = encode_jwt(
        {
            "sub": uuid.uuid4(),
            "sid": uuid.uuid4(),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=30),
            "exp": datetime.now(UTC) - timedelta(minutes=15),
        }
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(get_current_user(credentials=credentials, db=None))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Access token has expired."


def test_request_password_reset_creates_hashed_token_notification_and_audit():
    user = make_user()
    db = CapturingSession(results=[[user], None, None])

    asyncio.run(
        request_password_reset(
            db,
            payload=ForgotPasswordRequest(
                email=user.email,
                organization_id=user.organization_id,
            ),
        )
    )

    action_token = next(value for value in db.added if isinstance(value, AuthActionToken))
    notification = next(value for value in db.added if isinstance(value, Notification))
    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    reset_url = notification.payload["url"]
    raw_token = reset_url.rsplit("token=", 1)[1]

    assert db.committed is True
    assert action_token.purpose == AuthActionTokenPurpose.PASSWORD_RESET
    assert action_token.token_hash == hash_action_token(raw_token)
    assert action_token.token_hash != raw_token
    assert notification.recipient_contact == user.email
    assert notification.payload["action"] == "password_reset"
    assert audit_log.action == "auth.password_reset.requested"


def test_request_password_reset_does_not_reveal_missing_or_ambiguous_account():
    db = CapturingSession(results=[[]])

    asyncio.run(
        request_password_reset(
            db,
            payload=ForgotPasswordRequest(email="missing@example.com"),
        )
    )

    assert db.added == []
    assert db.committed is False


def test_validate_action_token_rejects_wrong_or_missing_purpose():
    db = CapturingSession(results=[None])

    with pytest.raises(InvalidAuthActionToken):
        asyncio.run(
            validate_action_token(
                db,
                token="raw-token",
                purpose=AuthActionTokenPurpose.PASSWORD_RESET,
                now=datetime.now(UTC),
            )
        )


def test_reset_password_consumes_token_changes_password_and_revokes_sessions():
    user = make_user()
    raw_token = "r" * 40
    action_token = AuthActionToken(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=user.organization_id,
        purpose=AuthActionTokenPurpose.PASSWORD_RESET,
        token_hash=hash_action_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    action_token.user = user
    db = CapturingSession(results=[action_token, None])

    asyncio.run(
        reset_password(
            db,
            payload=ResetPasswordRequest(
                token=raw_token,
                new_password="new-password",
            ),
        )
    )

    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    assert db.committed is True
    assert action_token.used_at is not None
    assert verify_password("new-password", user.auth_methods[0].password_hash)
    assert not verify_password("old-password", user.auth_methods[0].password_hash)
    assert audit_log.action == "auth.password_reset.completed"
    assert any("sessions" in str(statement) for statement in db.statements)


def test_verify_email_sets_email_verified_and_consumes_token():
    user = make_user(email_verified=False)
    raw_token = "v" * 40
    action_token = AuthActionToken(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=user.organization_id,
        purpose=AuthActionTokenPurpose.EMAIL_VERIFICATION,
        token_hash=hash_action_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    action_token.user = user
    db = CapturingSession(results=[action_token])

    asyncio.run(
        verify_email(
            db,
            payload=VerifyEmailRequest(token=raw_token),
        )
    )

    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    assert db.committed is True
    assert user.email_verified is True
    assert action_token.used_at is not None
    assert audit_log.action == "auth.email_verified"


def test_resend_email_verification_rate_limits_recent_request():
    user = make_user(email_verified=False)
    db = CapturingSession(results=[[user], uuid.uuid4()])

    with pytest.raises(AuthActionRateLimited):
        asyncio.run(
            resend_email_verification(
                db,
                payload=ResendVerificationRequest(
                    email=user.email,
                    organization_id=user.organization_id,
                ),
            )
        )

    assert db.added == []
    assert db.committed is False


def test_resend_email_verification_creates_token_notification_and_resent_audit():
    user = make_user(email_verified=False)
    db = CapturingSession(results=[[user], None, None])

    asyncio.run(
        resend_email_verification(
            db,
            payload=ResendVerificationRequest(
                email=user.email,
                organization_id=user.organization_id,
            ),
        )
    )

    action_token = next(value for value in db.added if isinstance(value, AuthActionToken))
    notification = next(value for value in db.added if isinstance(value, Notification))
    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    raw_token = notification.payload["url"].rsplit("token=", 1)[1]

    assert db.committed is True
    assert action_token.purpose == AuthActionTokenPurpose.EMAIL_VERIFICATION
    assert action_token.token_hash == hash_action_token(raw_token)
    assert notification.payload["action"] == "email_verification"
    assert audit_log.action == "auth.email_verification.resent"


def test_resend_email_verification_noops_for_already_verified_user():
    user = make_user(email_verified=True)
    db = CapturingSession(results=[[user]])

    asyncio.run(
        resend_email_verification(
            db,
            payload=ResendVerificationRequest(
                email=user.email,
                organization_id=user.organization_id,
            ),
        )
    )

    assert db.added == []
    assert db.committed is False
