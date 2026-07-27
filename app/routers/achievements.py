import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import Achievement
from app.models.enums import AchievementPosition
from app.models.user import User
from app.schemas.achievements import (
    AchievementCreate,
    AchievementResponse,
    AchievementUpdate,
    PaginatedAchievementsResponse,
)
from app.services.broadcast import broadcast_event

router = APIRouter(prefix="/api/achievements", tags=["Achievements"])


@router.get("", response_model=PaginatedAchievementsResponse)
async def list_achievements(
    year: Optional[int] = Query(None, description="Filter by year"),
    position: Optional[AchievementPosition] = Query(None, description="Filter by position"),
    event_id: Optional[uuid.UUID] = Query(None, description="Filter by event ID"),
    student_id: Optional[uuid.UUID] = Query(None, description="Filter by student ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Achievement)
    count_query = select(func.count(Achievement.id))

    if year:
        query = query.filter(Achievement.year == year)
        count_query = count_query.filter(Achievement.year == year)
    if position:
        query = query.filter(Achievement.position == position)
        count_query = count_query.filter(Achievement.position == position)
    if event_id:
        query = query.filter(Achievement.event_id == event_id)
        count_query = count_query.filter(Achievement.event_id == event_id)
    if student_id:
        query = query.filter(Achievement.student_id == student_id)
        count_query = count_query.filter(Achievement.student_id == student_id)

    query = query.order_by(Achievement.year.desc(), Achievement.created_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedAchievementsResponse(
        items=[AchievementResponse.model_validate(a) for a in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Achievement).filter_by(id=achievement_id))
    achievement = res.scalars().first()
    if not achievement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
    return achievement


@router.post("", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    body: AchievementCreate,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    achievement = Achievement(**body.model_dump())
    db.add(achievement)
    await db.commit()
    await db.refresh(achievement)

    payload = AchievementResponse.model_validate(achievement).model_dump(mode="json")
    await broadcast_event("achievement.created", payload)
    return achievement


@router.put("/{achievement_id}", response_model=AchievementResponse)
async def update_achievement(
    achievement_id: uuid.UUID,
    body: AchievementUpdate,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Achievement).filter_by(id=achievement_id))
    achievement = res.scalars().first()
    if not achievement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(achievement, f, v)

    await db.commit()
    await db.refresh(achievement)

    payload = AchievementResponse.model_validate(achievement).model_dump(mode="json")
    await broadcast_event("achievement.updated", payload)
    return achievement


@router.delete("/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_achievement(
    achievement_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Achievement).filter_by(id=achievement_id))
    achievement = res.scalars().first()
    if not achievement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")

    ach_id_str = str(achievement.id)
    await db.delete(achievement)
    await db.commit()

    await broadcast_event("achievement.deleted", {"achievement_id": ach_id_str})
    return None
