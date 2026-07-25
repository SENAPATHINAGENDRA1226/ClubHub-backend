import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import Alumni
from app.models.user import User
from app.schemas.alumni import (
    AlumniCreate,
    AlumniInviteResponse,
    AlumniPublicCreate,
    AlumniResponse,
    AlumniUpdate,
    PaginatedAlumniResponse,
)
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/alumni", tags=["Alumni"])


@router.get("", response_model=PaginatedAlumniResponse)
async def list_alumni(
    graduation_year: Optional[int] = Query(None, description="Filter by graduation year"),
    branch: Optional[str] = Query(None, description="Filter by branch"),
    is_published: Optional[bool] = Query(True, description="Filter by published status"),
    status_filter: Optional[str] = Query(None, alias="status", description="pending/approved/rejected/all"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Alumni)
    count_query = select(func.count(Alumni.id))

    # Status filter maps to is_published
    if status_filter == "pending":
        query = query.filter(Alumni.is_published == False)
        count_query = count_query.filter(Alumni.is_published == False)
    elif status_filter == "approved":
        query = query.filter(Alumni.is_published == True)
        count_query = count_query.filter(Alumni.is_published == True)
    elif status_filter == "all":
        pass  # No filter
    elif is_published is not None:
        query = query.filter(Alumni.is_published == is_published)
        count_query = count_query.filter(Alumni.is_published == is_published)

    if graduation_year:
        query = query.filter(Alumni.graduation_year == graduation_year)
        count_query = count_query.filter(Alumni.graduation_year == graduation_year)
    if branch:
        query = query.filter(func.lower(Alumni.branch) == branch.lower())
        count_query = count_query.filter(func.lower(Alumni.branch) == branch.lower())

    query = query.order_by(Alumni.graduation_year.desc(), Alumni.full_name.asc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    alumni_list = res.scalars().all()

    return PaginatedAlumniResponse(
        items=[AlumniResponse.model_validate(a) for a in alumni_list],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{alumni_id}", response_model=AlumniResponse)
async def get_alumni(
    alumni_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Alumni).filter_by(id=alumni_id))
    alumni_entry = res.scalars().first()
    if not alumni_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumni record not found")
    return alumni_entry


@router.post("", response_model=AlumniResponse, status_code=status.HTTP_201_CREATED)
async def create_alumni(
    body: AlumniCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    alumni_entry = Alumni(
        **body.model_dump(),
        added_by=current_user.id,
    )
    db.add(alumni_entry)
    await db.commit()
    await db.refresh(alumni_entry)

    payload = AlumniResponse.model_validate(alumni_entry).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="alumni",
        entity_id=alumni_entry.id,
        payload={"full_name": alumni_entry.full_name},
    )

    await broadcast(
        channel="alumni",
        event_type="alumni.created",
        entity_id=str(alumni_entry.id),
        action="created",
        payload=payload,
    )

    return alumni_entry


@router.put("/{alumni_id}", response_model=AlumniResponse)
async def update_alumni(
    alumni_id: uuid.UUID,
    body: AlumniUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Alumni).filter_by(id=alumni_id))
    alumni_entry = res.scalars().first()
    if not alumni_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumni record not found")

    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(alumni_entry, f, v)

    await db.commit()
    await db.refresh(alumni_entry)

    payload = AlumniResponse.model_validate(alumni_entry).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="updated",
        entity_type="alumni",
        entity_id=alumni_entry.id,
        payload={"full_name": alumni_entry.full_name},
    )

    await broadcast(
        channel="alumni",
        event_type="alumni.updated",
        entity_id=str(alumni_entry.id),
        action="updated",
        payload=payload,
    )

    return alumni_entry


@router.delete("/{alumni_id}", response_model=AlumniResponse)
async def delete_alumni(
    alumni_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Alumni).filter_by(id=alumni_id))
    alumni_entry = res.scalars().first()
    if not alumni_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumni record not found")

    response_data = AlumniResponse.model_validate(alumni_entry).model_dump(mode="json")
    a_id_str = str(alumni_entry.id)
    a_name = alumni_entry.full_name

    await db.delete(alumni_entry)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="alumni",
        payload={"full_name": a_name, "alumni_id": a_id_str},
    )

    await broadcast(
        channel="alumni",
        event_type="alumni.deleted",
        entity_id=a_id_str,
        action="deleted",
        payload={"alumni_id": a_id_str, "full_name": a_name},
    )

    return AlumniResponse(**response_data)


@router.post("/invite", response_model=AlumniInviteResponse)
async def generate_invite_link(
    current_user: User = Depends(require_role("admin")),
):
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": "alumni_invite", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    # The frontend will build the full URL (e.g., https://site/alumni/join?token=...)
    # We return just the token here, or a relative pattern
    return AlumniInviteResponse(invite_url=f"/alumni/join?token={encoded_jwt}")


@router.post("/public", response_model=AlumniResponse, status_code=status.HTTP_201_CREATED)
async def submit_public_alumni(
    body: AlumniPublicCreate,
    db: AsyncSession = Depends(get_async_session),
):
    # Verify token
    try:
        payload = jwt.decode(body.token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("sub") != "alumni_invite":
            raise HTTPException(status_code=403, detail="Invalid invite token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Invite token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid invite token")

    data = body.model_dump(exclude={"token"})
    alumni_entry = Alumni(
        **data,
        is_published=False,  # Needs admin approval
    )
    db.add(alumni_entry)
    await db.commit()
    await db.refresh(alumni_entry)

    # Notify admin
    await broadcast(
        channel="alumni",
        event_type="alumni.submitted",
        entity_id=str(alumni_entry.id),
        action="submitted",
        payload={"id": str(alumni_entry.id), "name": alumni_entry.full_name},
    )

    return alumni_entry


@router.patch("/{alumni_id}/publish", response_model=AlumniResponse)
async def publish_alumni(
    alumni_id: uuid.UUID,
    is_published: bool = Query(..., description="Set to true to publish, false to unpublish"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Alumni).filter_by(id=alumni_id))
    alumni_entry = res.scalars().first()
    if not alumni_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumni record not found")

    alumni_entry.is_published = is_published
    await db.commit()
    await db.refresh(alumni_entry)

    payload = AlumniResponse.model_validate(alumni_entry).model_dump(mode="json")
    action = "approved" if is_published else "rejected"

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action=action,
        entity_type="alumni",
        entity_id=alumni_entry.id,
        payload={"full_name": alumni_entry.full_name},
    )

    await broadcast(
        channel="alumni",
        event_type=f"alumni.{action}",
        entity_id=str(alumni_entry.id),
        action=action,
        payload=payload,
    )

    return alumni_entry
