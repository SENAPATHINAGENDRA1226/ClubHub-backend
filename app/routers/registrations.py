import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.enums import EventCategory, RegistrationStatus
from app.models.event import Event, EventRegistration
from app.models.user import StudentProfile, User
from app.schemas.registrations import (
    PaginatedRegistrationsResponse,
    RegistrationCreate,
    RegistrationResponse,
    AchievementUpdate,
)
from app.models.content import Achievement
from fastapi.responses import Response
from app.services.broadcast import broadcast_event
from app.services.qr import generate_registration_qr, generate_qr_png_bytes

router = APIRouter(prefix="/api/registrations", tags=["Event Registrations"])


@router.post("", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_for_event(
    body: RegistrationCreate,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_async_session),
):
    # 1. Fetch Student Profile
    sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
    student_profile = sp_res.scalars().first()
    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile not found. Please complete signup/onboarding first.",
        )

    # 2. Fetch Event
    e_res = await db.execute(select(Event).filter_by(id=body.event_id, is_active=True))
    event = e_res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found or inactive",
        )

    # 3. Category Validation (Only category='current' allowed)
    cat_val = event.category.value if hasattr(event.category, "value") else str(event.category)
    if cat_val != EventCategory.CURRENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration is only allowed for 'current' events (event status: '{cat_val}')",
        )

    # 4. Deadline Check
    now_utc = datetime.now(timezone.utc)
    if event.registration_deadline and now_utc > event.registration_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration deadline has passed for this event",
        )

    # 5. Duplicate Check
    dup_res = await db.execute(
        select(EventRegistration).filter_by(
            event_id=event.id,
            student_id=student_profile.id,
        )
    )
    if dup_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already registered for this event",
        )

    # 6. Max Participants Check
    if event.max_participants is not None:
        count_res = await db.execute(
            select(func.count(EventRegistration.id)).filter_by(event_id=event.id)
        )
        current_count = count_res.scalar() or 0
        if current_count >= event.max_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event capacity reached. Registration closed.",
            )

    # 7. Generate Registration Number (CH-{year}-{seq6})
    total_reg_res = await db.execute(select(func.count(EventRegistration.id)))
    total_seq = (total_reg_res.scalar() or 0) + 1
    reg_number = f"CH-{event.event_year}-{total_seq:06d}"

    # 8. Generate HMAC Signed QR Payload & Image
    qr_data, qr_image_url = generate_registration_qr(
        registration_number=reg_number,
        event_id=event.id,
        student_id=student_profile.id,
    )

    # 9. Create Registration Record
    registration = EventRegistration(
        event_id=event.id,
        student_id=student_profile.id,
        registration_number=reg_number,
        qr_code_data=qr_data,
        qr_code_image_url=qr_image_url,
        status=RegistrationStatus.PENDING,
        registered_at=now_utc,
    )
    db.add(registration)
    await db.commit()

    # Re-query with relationships loaded
    q = (
        select(EventRegistration)
        .options(
            selectinload(EventRegistration.event),
            selectinload(EventRegistration.student),
        )
        .filter_by(id=registration.id)
    )
    res = await db.execute(q)
    full_registration = res.scalars().first()

    reg_payload = RegistrationResponse.model_validate(full_registration).model_dump(mode="json")
    await broadcast_event("registration.created", reg_payload)

    return full_registration


@router.get("/me", response_model=PaginatedRegistrationsResponse)
async def get_my_registrations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
    student_profile = sp_res.scalars().first()
    if not student_profile:
        return PaginatedRegistrationsResponse(items=[], total=0, limit=limit, offset=offset)

    query = (
        select(EventRegistration)
        .options(selectinload(EventRegistration.event))
        .filter_by(student_id=student_profile.id)
        .order_by(EventRegistration.registered_at.desc())
    )
    count_query = (
        select(func.count(EventRegistration.id))
        .filter_by(student_id=student_profile.id)
    )

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    registrations = res.scalars().all()

    return PaginatedRegistrationsResponse(
        items=[RegistrationResponse.model_validate(r) for r in registrations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/event/{event_id}", response_model=PaginatedRegistrationsResponse)
async def list_event_registrations(
    event_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    query = (
        select(EventRegistration)
        .options(
            selectinload(EventRegistration.student),
            selectinload(EventRegistration.event),
        )
        .filter_by(event_id=event_id)
        .order_by(EventRegistration.registered_at.desc())
    )
    count_query = select(func.count(EventRegistration.id)).filter_by(event_id=event_id)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    registrations = res.scalars().all()

    return PaginatedRegistrationsResponse(
        items=[RegistrationResponse.model_validate(r) for r in registrations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{registration_id}/achievement", response_model=RegistrationResponse)
async def update_registration_achievement(
    registration_id: uuid.UUID,
    body: AchievementUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    # 1. Fetch Registration
    q = (
        select(EventRegistration)
        .options(
            selectinload(EventRegistration.event),
            selectinload(EventRegistration.student),
        )
        .filter_by(id=registration_id)
    )
    res = await db.execute(q)
    registration = res.scalars().first()
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration not found",
        )

    # 2. Update fields
    registration.achievement_position = body.achievement_position
    if body.certificate_url_override is not None:
        registration.certificate_url_override = body.certificate_url_override
    
    # 3. Auto-generate achievement if WINNER or RUNNER_UP
    if body.achievement_position in ["winner", "runner_up"]:
        # Check if achievement already exists
        ach_q = select(Achievement).filter_by(
            student_id=registration.student_id,
            event_id=registration.event_id
        )
        ach_res = await db.execute(ach_q)
        achievement = ach_res.scalars().first()
        
        pos_title = "Winner" if body.achievement_position == "winner" else "Runner Up"
        title_str = f"{pos_title} - {registration.event.title}"
        desc_str = f"Awarded {pos_title} position at {registration.event.title}."
        
        if not achievement:
            achievement = Achievement(
                student_id=registration.student_id,
                event_id=registration.event_id,
                title=title_str,
                description=desc_str,
                position=body.achievement_position,
                year=registration.event.event_year,
            )
            db.add(achievement)
        else:
            achievement.title = title_str
            achievement.description = desc_str
            achievement.position = body.achievement_position
    
    await db.commit()
    await db.refresh(registration)
    
    return RegistrationResponse.model_validate(registration)


@router.get("/qr/{filename}")
async def get_registration_qr_image(
    filename: str,
    db: AsyncSession = Depends(get_async_session),
):
    clean_num = filename.replace(".png", "")

    try:
        uuid_obj = uuid.UUID(clean_num)
        query = select(EventRegistration).filter(
            (EventRegistration.registration_number == clean_num) |
            (EventRegistration.id == uuid_obj)
        )
    except ValueError:
        query = select(EventRegistration).filter(
            EventRegistration.registration_number == clean_num
        )

    res = await db.execute(query)
    reg = res.scalars().first()
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR image not found")

    qr_data = reg.qr_code_data
    if not qr_data:
        qr_data, _ = generate_registration_qr(
            registration_number=reg.registration_number,
            event_id=reg.event_id,
            student_id=reg.student_id,
        )

    img_bytes = generate_qr_png_bytes(qr_data)
    return Response(content=img_bytes, media_type="image/png")


