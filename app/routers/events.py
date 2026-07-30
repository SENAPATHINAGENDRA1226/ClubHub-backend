import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.content import Announcement, Certificate
from app.models.enums import EventCategory
from app.models.event import Event, EventRegistration
from app.models.user import User
from app.schemas.events import EventCreate, EventResponse, EventUpdate, PaginatedEventsResponse
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=PaginatedEventsResponse)
async def list_events(
    category: Optional[EventCategory] = Query(None, description="Filter by event category"),
    year: Optional[int] = Query(None, description="Filter by event year (required for past events)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Event).filter(Event.is_active == True)
    count_query = select(func.count(Event.id)).filter(Event.is_active == True)

    if category:
        query = query.filter(Event.category == category)
        count_query = count_query.filter(Event.category == category)

    if year:
        query = query.filter(Event.event_year == year)
        count_query = count_query.filter(Event.event_year == year)

    # Order events logically: upcoming/current by event_date asc, past by event_date desc
    if category == EventCategory.PAST:
        query = query.order_by(Event.event_date.desc())
    else:
        query = query.order_by(Event.event_date.asc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    events = res.scalars().all()

    return PaginatedEventsResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin", response_model=PaginatedEventsResponse)
async def list_events_admin(
    search: Optional[str] = Query(None, description="Search by title"),
    category: Optional[EventCategory] = Query(None),
    year: Optional[int] = Query(None),
    sort_by: Optional[str] = Query("event_date", description="Sort column"),
    sort_dir: Optional[str] = Query("desc", description="asc or desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    """Admin list: all events (including inactive), with search and sort."""
    query = select(Event).filter(Event.is_active == True)
    count_query = select(func.count(Event.id)).filter(Event.is_active == True)

    if category:
        query = query.filter(Event.category == category)
        count_query = count_query.filter(Event.category == category)
    if year:
        query = query.filter(Event.event_year == year)
        count_query = count_query.filter(Event.event_year == year)
    if search:
        query = query.filter(Event.title.ilike(f"%{search}%"))
        count_query = count_query.filter(Event.title.ilike(f"%{search}%"))

    # Dynamic sort
    sort_col = getattr(Event, sort_by, Event.event_date)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    events = res.scalars().all()

    return PaginatedEventsResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/years", response_model=List[int])
async def get_event_years(
    db: AsyncSession = Depends(get_async_session),
):
    query = (
        select(Event.event_year)
        .filter(Event.is_active == True)
        .distinct()
        .order_by(Event.event_year.desc())
    )
    res = await db.execute(query)
    years = res.scalars().all()
    return list(years)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Event).filter(Event.id == event_id, Event.is_active == True))
    event = res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.get("/{event_id}/registration-count")
async def get_event_registration_count(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    count_res = await db.execute(
        select(func.count(EventRegistration.id)).filter_by(event_id=event_id)
    )
    return {"event_id": str(event_id), "count": count_res.scalar() or 0}


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    event = Event(
        **body.model_dump(),
        created_by=current_user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    event_data = EventResponse.model_validate(event).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="event",
        entity_id=event.id,
        payload={"title": event.title},
    )

    await broadcast(
        channel="events",
        event_type="events.created",
        entity_id=str(event.id),
        action="created",
        payload=event_data,
    )

    return event


@router.post("/{event_id}/duplicate", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_event(
    event_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Clone an existing event for quick re-creation (e.g. recurring annual events)."""
    res = await db.execute(select(Event).filter_by(id=event_id))
    source = res.scalars().first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    from datetime import datetime, timezone

    new_event = Event(
        title=f"{source.title} (Copy)",
        description=source.description,
        category=EventCategory.UPCOMING,
        event_date=source.event_date,
        event_year=datetime.now(timezone.utc).year,
        location=source.location,
        banner_image_url=source.banner_image_url,
        max_participants=source.max_participants,
        registration_deadline=source.registration_deadline,
        is_active=False,  # Draft — admin edits before activating
        certificate_url_pattern=source.certificate_url_pattern,
        created_by=current_user.id,
    )
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)

    event_data = EventResponse.model_validate(new_event).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="duplicated",
        entity_type="event",
        entity_id=new_event.id,
        payload={"source_event_id": str(event_id), "title": new_event.title},
    )

    await broadcast(
        channel="events",
        event_type="events.created",
        entity_id=str(new_event.id),
        action="created",
        payload=event_data,
    )

    return new_event


@router.patch("/bulk-year")
async def bulk_update_event_year(
    event_ids: List[uuid.UUID] = Body(...),
    new_year: int = Body(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Bulk re-tag multiple events with a different event_year."""
    res = await db.execute(select(Event).filter(Event.id.in_(event_ids)))
    events = res.scalars().all()

    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching events found")

    updated_ids = []
    for event in events:
        event.event_year = new_year
        updated_ids.append(str(event.id))

    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="bulk_year_updated",
        entity_type="event",
        payload={"event_ids": updated_ids, "new_year": new_year},
    )

    await broadcast(
        channel="events",
        event_type="events.updated",
        action="bulk_updated",
        payload={"event_ids": updated_ids, "new_year": new_year},
    )

    return {"updated_count": len(updated_ids), "new_year": new_year}


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Event).filter_by(id=event_id))
    event = res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(event, field, val)

    await db.commit()
    await db.refresh(event)

    event_data = EventResponse.model_validate(event).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="updated",
        entity_type="event",
        entity_id=event.id,
        payload={"title": event.title, "fields": list(update_data.keys())},
    )

    await broadcast(
        channel="events",
        event_type="events.updated",
        entity_id=str(event.id),
        action="updated",
        payload=event_data,
    )

    return event


@router.delete("/{event_id}", response_model=EventResponse)
async def delete_event(
    event_id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Event).filter_by(id=event_id))
    event = res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    # Clean up event registrations, certificates, and announcements explicitly
    reg_res = await db.execute(select(EventRegistration).filter_by(event_id=event_id))
    for r in reg_res.scalars().all():
        await db.delete(r)

    cert_res = await db.execute(select(Certificate).filter_by(event_id=event_id))
    for c in cert_res.scalars().all():
        await db.delete(c)

    ann_res = await db.execute(select(Announcement).filter_by(event_id=event_id))
    for a in ann_res.scalars().all():
        await db.delete(a)

    event_data = EventResponse.model_validate(event).model_dump(mode="json")
    event_id_str = str(event.id)
    event_title = event.title

    event.is_active = False
    await db.delete(event)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="event",
        payload={"title": event_title, "event_id": event_id_str},
    )

    await broadcast(
        channel="events",
        event_type="events.deleted",
        entity_id=event_id_str,
        action="deleted",
        payload={"event_id": event_id_str, "title": event_title},
    )

    return EventResponse(**event_data)
