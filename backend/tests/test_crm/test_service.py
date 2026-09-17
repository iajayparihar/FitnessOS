import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.crm.exceptions import (
    FollowUpAlreadyCompleted,
    FollowUpNotFound,
    LeadAlreadyConverted,
    LeadNotFound,
    LeadSourceConflict,
)
from app.modules.crm.models import (
    Lead,
    LeadActivity,
    LeadFollowUp,
    LeadFollowUpType,
    LeadSource,
    LeadStatus,
)
from app.modules.crm.schemas import (
    FollowUpCompleteRequest,
    FollowUpCreate,
    LeadConvertRequest,
    LeadCreate,
    LeadLostRequest,
    LeadSourceCreate,
)
from app.modules.crm.service import (
    complete_follow_up,
    convert_lead,
    create_follow_up,
    create_lead,
    create_lead_source,
    get_lead,
    list_leads,
    mark_lead_lost,
)


class _Result:
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


class FakeSession:
    def __init__(self, results=()):
        self.results = list(results)
        self.statements = []
        self.added = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.results.pop(0))

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if hasattr(value, "id") and getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        return None


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


ORG = uuid.uuid4()


def test_create_lead_source_rejects_duplicate():
    db = FakeSession(results=[uuid.uuid4()])  # existing id -> conflict

    with pytest.raises(LeadSourceConflict):
        asyncio.run(
            create_lead_source(
                db, organization_id=ORG, payload=LeadSourceCreate(name="Walk-in")
            )
        )


def test_create_lead_source_creates_when_unique():
    db = FakeSession(results=[None])

    asyncio.run(
        create_lead_source(
            db, organization_id=ORG, payload=LeadSourceCreate(name="Walk-in")
        )
    )

    assert any(isinstance(v, LeadSource) for v in db.added)
    assert db.committed is True


def test_create_lead_records_activity():
    db = FakeSession(results=[])  # no source_id -> no lookup

    lead = asyncio.run(
        create_lead(
            db,
            organization_id=ORG,
            payload=LeadCreate(first_name="Ada", email="ADA@Example.com"),
            actor_id=uuid.uuid4(),
        )
    )

    assert isinstance(lead, Lead)
    assert lead.email == "ada@example.com"
    assert lead.status == LeadStatus.NEW
    assert any(isinstance(v, LeadActivity) for v in db.added)
    assert db.committed is True


def test_get_lead_missing_raises():
    db = FakeSession(results=[None])

    with pytest.raises(LeadNotFound):
        asyncio.run(get_lead(db, organization_id=ORG, lead_id=uuid.uuid4()))


def test_list_leads_returns_rows_and_total_and_is_tenant_scoped():
    leads = [Lead(id=uuid.uuid4(), organization_id=ORG, status=LeadStatus.NEW)]
    db = FakeSession(results=[1, leads])  # scalar(count), then execute(select)

    rows, total = asyncio.run(list_leads(db, organization_id=ORG, page=1, page_size=20))

    assert total == 1
    assert rows == leads
    assert "leads.organization_id" in _compile(db.statements[1])


def test_convert_lead_sets_converted_fields():
    lead = Lead(id=uuid.uuid4(), organization_id=ORG, status=LeadStatus.NEW)
    db = FakeSession(results=[lead])

    result = asyncio.run(
        convert_lead(
            db,
            organization_id=ORG,
            lead_id=lead.id,
            payload=LeadConvertRequest(),
        )
    )

    assert result.status == LeadStatus.CONVERTED
    assert result.converted_at is not None
    assert any(isinstance(v, LeadActivity) for v in db.added)


def test_convert_lead_twice_raises():
    lead = Lead(
        id=uuid.uuid4(),
        organization_id=ORG,
        status=LeadStatus.CONVERTED,
        converted_at=datetime.now(UTC),
    )
    db = FakeSession(results=[lead])

    with pytest.raises(LeadAlreadyConverted):
        asyncio.run(
            convert_lead(
                db, organization_id=ORG, lead_id=lead.id, payload=LeadConvertRequest()
            )
        )


def test_mark_lead_lost_sets_reason():
    lead = Lead(id=uuid.uuid4(), organization_id=ORG, status=LeadStatus.NEW)
    db = FakeSession(results=[lead])

    result = asyncio.run(
        mark_lead_lost(
            db,
            organization_id=ORG,
            lead_id=lead.id,
            payload=LeadLostRequest(lost_reason="Too expensive"),
        )
    )

    assert result.status == LeadStatus.LOST
    assert result.lost_reason == "Too expensive"


def test_create_follow_up_requires_existing_lead():
    lead = Lead(id=uuid.uuid4(), organization_id=ORG, status=LeadStatus.NEW)
    db = FakeSession(results=[lead])

    follow_up = asyncio.run(
        create_follow_up(
            db,
            organization_id=ORG,
            lead_id=lead.id,
            payload=FollowUpCreate(
                type=LeadFollowUpType.CALL,
                scheduled_at=datetime.now(UTC) + timedelta(days=1),
            ),
        )
    )

    assert isinstance(follow_up, LeadFollowUp)
    assert db.committed is True


def test_complete_follow_up_missing_raises():
    db = FakeSession(results=[None])

    with pytest.raises(FollowUpNotFound):
        asyncio.run(
            complete_follow_up(
                db,
                organization_id=ORG,
                follow_up_id=uuid.uuid4(),
                payload=FollowUpCompleteRequest(),
            )
        )


def test_complete_follow_up_twice_raises():
    follow_up = LeadFollowUp(
        id=uuid.uuid4(),
        organization_id=ORG,
        lead_id=uuid.uuid4(),
        type=LeadFollowUpType.CALL,
        scheduled_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db = FakeSession(results=[follow_up])

    with pytest.raises(FollowUpAlreadyCompleted):
        asyncio.run(
            complete_follow_up(
                db,
                organization_id=ORG,
                follow_up_id=follow_up.id,
                payload=FollowUpCompleteRequest(),
            )
        )


def test_complete_follow_up_sets_completed_at():
    follow_up = LeadFollowUp(
        id=uuid.uuid4(),
        organization_id=ORG,
        lead_id=uuid.uuid4(),
        type=LeadFollowUpType.CALL,
        scheduled_at=datetime.now(UTC),
    )
    db = FakeSession(results=[follow_up])

    result = asyncio.run(
        complete_follow_up(
            db,
            organization_id=ORG,
            follow_up_id=follow_up.id,
            payload=FollowUpCompleteRequest(outcome="Joined"),
        )
    )

    assert result.completed_at is not None
    assert result.outcome == "Joined"
