from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.tenants.dependencies import get_current_org
from app.modules.tenants.models import Organization
from app.modules.tenants.schemas import OrgCreate, OrgEnvelope
from app.modules.tenants.service import create_org, ensure_slug_available, make_slug

router = APIRouter()


@router.post("", response_model=OrgEnvelope, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrgCreate,
    db: AsyncSession = Depends(get_db),
) -> OrgEnvelope:
    """Create an organization tenant."""
    slug = make_slug(payload.slug or payload.name)
    try:
        await ensure_slug_available(db, slug=slug)
        organization = await create_org(
            db,
            payload=payload.model_copy(update={"slug": slug}),
        )
        await db.commit()
        await db.refresh(organization)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already exists.",
        ) from exc

    return OrgEnvelope(data=organization)


@router.get("/current", response_model=OrgEnvelope)
async def current_organization(
    organization: Organization = Depends(get_current_org),
) -> OrgEnvelope:
    """Return the authenticated user's organization tenant."""
    return OrgEnvelope(data=organization)
