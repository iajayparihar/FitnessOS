from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType
from app.modules.analytics.models import AuditLog


async def log_audit_event(
    db: AsyncSession,
    *,
    action: str,
    organization_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_type: ActorType = ActorType.USER,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an audit event without committing the caller's transaction."""
    audit_log = AuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_=metadata,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log
