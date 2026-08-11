import asyncio
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.rbac.exceptions import BranchNotInOrganization
from app.modules.rbac.models import Role
from app.modules.rbac.service import assign_role_to_user, user_has_permission


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class CapturingSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return ScalarResult(self.results.pop(0))

    def add(self, _value):
        raise AssertionError("Unexpected write")

    async def flush(self):
        raise AssertionError("Unexpected flush")


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
