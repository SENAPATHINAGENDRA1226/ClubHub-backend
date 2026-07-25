import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import Opportunity
from app.models.enums import OpportunityType
from app.models.user import User
from app.schemas.opportunities import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
    PaginatedOpportunitiesResponse,
)
from app.services.broadcast import broadcast_event

router = APIRouter(prefix="/api/opportunities", tags=["Opportunities"])


@router.get("", response_model=PaginatedOpportunitiesResponse)
async def list_opportunities(
    opportunity_type: Optional[OpportunityType] = Query(None, description="Filter by opportunity type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Opportunity)
    count_query = select(func.count(Opportunity.id))

    if opportunity_type:
        query = query.filter(Opportunity.opportunity_type == opportunity_type)
        count_query = count_query.filter(Opportunity.opportunity_type == opportunity_type)

    query = query.order_by(Opportunity.created_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedOpportunitiesResponse(
        items=[OpportunityResponse.model_validate(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Opportunity).filter_by(id=opportunity_id))
    opportunity = res.scalars().first()
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    body: OpportunityCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    opportunity = Opportunity(
        **body.model_dump(),
        posted_by=current_user.id,
    )
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)

    payload = OpportunityResponse.model_validate(opportunity).model_dump(mode="json")
    await broadcast_event("opportunity.created", payload)
    return opportunity


@router.put("/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: uuid.UUID,
    body: OpportunityUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Opportunity).filter_by(id=opportunity_id))
    opportunity = res.scalars().first()
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(opportunity, f, v)

    await db.commit()
    await db.refresh(opportunity)

    payload = OpportunityResponse.model_validate(opportunity).model_dump(mode="json")
    await broadcast_event("opportunity.updated", payload)
    return opportunity


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Opportunity).filter_by(id=opportunity_id))
    opportunity = res.scalars().first()
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    o_id_str = str(opportunity.id)
    await db.delete(opportunity)
    await db.commit()

    await broadcast_event("opportunity.deleted", {"opportunity_id": o_id_str})
    return None
