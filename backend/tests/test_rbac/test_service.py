import asyncio
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.analytics.models import AuditLog
from app.modules.rbac.exceptions import BranchNotInOrganization
from app.modules.rbac.models import Permission, Role, UserRole
from app.modules.rbac.schemas import RoleCreate
from app.modules.rbac.service import (
    assign_role_to_user,
    create_role,
    user_has_permission,
)


class QueryResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        if isinstance(self.value, list):
            return iter(self.value)
        if self.value is None:
            return iter(())
        return iter((self.value,))


class CapturingSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []
        self.added = []
        self.committed = False
        self.refreshed = []

    async def execute(self, statement):
        self.statements.append(statement)
        return QueryResult(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if hasattr(value, "id") and value.id is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed.append(value)


def compile_statement(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_user_has_permission_constrains_role_to_current_tenant_or_system_role():
    organization_id = uuid.uuid4()
    db = CapturingSession(results=[uuid.uuid4()])

    allowed = asyncio.run(
        user_has_permission(
            db,
            user_id=uuid.uuid4(),
            organization_id=organization_id,
            permission_code="rbac:read",
        )
    )

    assert allowed is True
    sql = compile_statement(db.statements[0])
    assert "user_roles.organization_id" in sql
    assert "roles.organization_id" in sql
    assert "roles.is_system IS true" in sql


def test_assign_role_to_user_rejects_branch_from_another_tenant():
    organization_id = uuid.uuid4()
    role = Role(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Manager",
        slug="manager",
        is_active=True,
    )
    db = CapturingSession(results=[role, uuid.uuid4(), None])

    with pytest.raises(BranchNotInOrganization):
        asyncio.run(
            assign_role_to_user(
                db,
                user_id=uuid.uuid4(),
                role_id=role.id,
                organization_id=organization_id,
                branch_id=uuid.uuid4(),
            )
        )


def test_create_role_audits_role_and_permissions():
    organization_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    permissions = [
        Permission(
            id=uuid.uuid4(),
            code="rbac:read",
            category="rbac",
            is_active=True,
        ),
        Permission(
            id=uuid.uuid4(),
            code="rbac:manage",
            category="rbac",
            is_active=True,
        ),
    ]
    db = CapturingSession(results=[permissions, permissions])

    role = asyncio.run(
        create_role(
            db,
            organization_id=organization_id,
            actor_id=actor_id,
            payload=RoleCreate(
                name="Security Admin",
                permission_codes=["rbac:read", "rbac:manage"],
            ),
        )
    )

    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    assert db.committed is True
    assert role in db.refreshed
    assert audit_log.action == "rbac.role.create"
    assert audit_log.organization_id == organization_id
    assert audit_log.actor_id == actor_id
    assert audit_log.target_type == "role"
    assert audit_log.target_id == role.id
    assert audit_log.after_state["slug"] == "security-admin"
    assert audit_log.after_state["permission_codes"] == ["rbac:read", "rbac:manage"]


def test_assign_role_to_user_audits_new_assignment():
    organization_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    role = Role(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Manager",
        slug="manager",
        is_active=True,
    )
    db = CapturingSession(results=[role, uuid.uuid4(), branch_id, None])

    assignment = asyncio.run(
        assign_role_to_user(
            db,
            user_id=uuid.uuid4(),
            role_id=role.id,
            organization_id=organization_id,
            assigned_by=actor_id,
            branch_id=branch_id,
        )
    )

    audit_log = next(value for value in db.added if isinstance(value, AuditLog))
    assert isinstance(assignment, UserRole)
    assert audit_log.action == "rbac.user_role.assign"
    assert audit_log.organization_id == organization_id
    assert audit_log.actor_id == actor_id
    assert audit_log.target_type == "user_role"
    assert audit_log.target_id == assignment.id
    assert audit_log.after_state["branch_id"] == str(branch_id)
