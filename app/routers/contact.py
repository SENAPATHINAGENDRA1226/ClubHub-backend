import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.misc import ContactMessage
from app.models.user import User
from app.schemas.contact import (
    ContactMessageCreate,
    ContactMessageResponse,
    PaginatedContactMessagesResponse,
)
from app.services.broadcast import broadcast_event

router = APIRouter(prefix="/api/contact", tags=["Contact Messages"])


@router.post("", response_model=ContactMessageResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact_message(
    body: ContactMessageCreate,
    db: AsyncSession = Depends(get_async_session),
):
    msg = ContactMessage(
        name=body.name,
        email=body.email,
        subject=body.subject,
        message=body.message,
        submitted_at=datetime.now(timezone.utc),
        is_read=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    payload = ContactMessageResponse.model_validate(msg).model_dump(mode="json")
    await broadcast_event("contact.submitted", payload)
    return msg


@router.get("", response_model=PaginatedContactMessagesResponse)
async def list_contact_messages(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(ContactMessage)
    count_query = select(func.count(ContactMessage.id))

    if is_read is not None:
        query = query.filter(ContactMessage.is_read == is_read)
        count_query = count_query.filter(ContactMessage.is_read == is_read)

    query = query.order_by(ContactMessage.submitted_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    items = res.scalars().all()

    return PaginatedContactMessagesResponse(
        items=[ContactMessageResponse.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{message_id}/read", response_model=ContactMessageResponse)
async def mark_contact_message_read(
    message_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(ContactMessage).filter_by(id=message_id))
    msg = res.scalars().first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.is_read = True
    await db.commit()
    await db.refresh(msg)

    return msg
