import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.enums import GrievanceStatus
from app.models.misc import Grievance
from app.models.user import StudentProfile, User
from app.schemas.grievances import (
    GrievanceCreate,
    GrievanceResponse,
    GrievanceUpdate,
    PaginatedGrievancesResponse,
)
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast


class GrievanceStatsResponse(BaseModel):
    total_open: int
    total_in_progress: int
    total_resolved: int
    category_distribution: Dict[str, int]
    avg_resolution_time_days: Optional[float]


router = APIRouter(prefix="/api/grievances", tags=["Grievances"])


@router.post("", response_model=GrievanceResponse, status_code=status.HTTP_201_CREATED)
async def submit_grievance(
    body: GrievanceCreate,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_async_session),
):
    sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
    student_profile = sp_res.scalars().first()
    if not student_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student profile required")

    grievance = Grievance(
        student_id=student_profile.id,
        subject=body.subject,
        message=body.message,
        category=body.category,
        is_anonymous=body.is_anonymous,
        status=GrievanceStatus.OPEN,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(grievance)
    await db.commit()
    await db.refresh(grievance)

    payload = GrievanceResponse.model_validate(grievance).model_dump(mode="json")

    await broadcast(
        channel="grievances",
        event_type="grievances.submitted",
        entity_id=str(grievance.id),
        action="submitted",
        payload=payload,
    )

    return grievance


@router.get("/me", response_model=PaginatedGrievancesResponse)
async def get_my_grievances(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_async_session),
):
    sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
    student_profile = sp_res.scalars().first()
    if not student_profile:
        return PaginatedGrievancesResponse(items=[], total=0, limit=limit, offset=offset)

    query = (
        select(Grievance)
        .filter_by(student_id=student_profile.id)
        .order_by(Grievance.submitted_at.desc())
    )
    count_query = select(func.count(Grievance.id)).filter_by(student_id=student_profile.id)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedGrievancesResponse(
        items=[GrievanceResponse.model_validate(g) for g in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=GrievanceStatsResponse)
async def get_grievance_stats(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    # Get all grievances
    res = await db.execute(select(Grievance))
    grievances = res.scalars().all()

    total_open = 0
    total_in_progress = 0
    total_resolved = 0
    category_distribution: Dict[str, int] = {}

    resolution_times: List[float] = []

    for g in grievances:
        if g.status == GrievanceStatus.OPEN:
            total_open += 1
        elif g.status == GrievanceStatus.IN_PROGRESS:
            total_in_progress += 1
        elif g.status == GrievanceStatus.RESOLVED:
            total_resolved += 1
            if g.resolved_at and g.submitted_at:
                delta = g.resolved_at - g.submitted_at
                resolution_times.append(delta.total_seconds() / 86400.0)  # in days

        cat_val = g.category.value if hasattr(g.category, "value") else str(g.category or "other")
        category_distribution[cat_val] = category_distribution.get(cat_val, 0) + 1

    avg_res_time = sum(resolution_times) / len(resolution_times) if resolution_times else None

    return GrievanceStatsResponse(
        total_open=total_open,
        total_in_progress=total_in_progress,
        total_resolved=total_resolved,
        category_distribution=category_distribution,
        avg_resolution_time_days=avg_res_time,
    )


@router.get("", response_model=PaginatedGrievancesResponse)
async def list_all_grievances(
    status_filter: Optional[GrievanceStatus] = Query(None, alias="status", description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Grievance)
    count_query = select(func.count(Grievance.id))

    if status_filter:
        query = query.filter(Grievance.status == status_filter)
        count_query = count_query.filter(Grievance.status == status_filter)

    if category:
        query = query.filter(Grievance.category == category)
        count_query = count_query.filter(Grievance.category == category)

    # Default sort: oldest unresolved first, then resolved by date desc
    from sqlalchemy import case
    query = query.order_by(
        case(
            (Grievance.status == GrievanceStatus.OPEN, 0),
            (Grievance.status == GrievanceStatus.IN_PROGRESS, 1),
            else_=2,
        ).asc(),
        Grievance.submitted_at.asc(),
    )

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedGrievancesResponse(
        items=[GrievanceResponse.model_validate(g) for g in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{grievance_id}", response_model=GrievanceResponse)
async def update_grievance(
    grievance_id: uuid.UUID,
    body: GrievanceUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Grievance).filter_by(id=grievance_id))
    grievance = res.scalars().first()
    if not grievance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance not found")

    action = "responded"

    if body.status:
        # Check transition to IN_PROGRESS
        if body.status == GrievanceStatus.IN_PROGRESS and grievance.status == GrievanceStatus.OPEN:
            grievance.under_review_at = datetime.now(timezone.utc)

        grievance.status = body.status
        if body.status == GrievanceStatus.RESOLVED:
            grievance.resolved_at = datetime.now(timezone.utc)
            action = "status_changed"
        else:
            action = "status_changed"

    if body.admin_response is not None:
        grievance.admin_response = body.admin_response
        action = "responded"

    await db.commit()
    await db.refresh(grievance)

    payload = GrievanceResponse.model_validate(grievance).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action=action,
        entity_type="grievance",
        entity_id=grievance.id,
        payload={"subject": grievance.subject, "status": grievance.status.value},
    )

    await broadcast(
        channel="grievances",
        event_type=f"grievances.{action}",
        entity_id=str(grievance.id),
        action=action,
        payload=payload,
    )

    return grievance
