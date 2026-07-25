import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.enums import RegistrationStatus
from app.models.event import Event, EventRegistration
from app.models.user import AdminProfile, StudentProfile, User
from app.schemas.verification import (
    ConfirmVerificationRequest,
    ScanQRRequest,
    VerificationPreviewResponse,
    VerificationStatsResponse,
)
from app.services.broadcast import broadcast_event
from app.services.audit import write_audit_log

router = APIRouter(prefix="/api/verify", tags=["QR Verification"])


async def _build_preview_response(
    reg: EventRegistration, db: AsyncSession
) -> VerificationPreviewResponse:
    student_name = reg.student.full_name if reg.student else "Student"
    student_photo = reg.student.profile_photo_url if reg.student else None
    branch = reg.student.branch if reg.student else ""
    section = reg.student.section if reg.student else ""
    academic_year = reg.student.academic_year if reg.student else ""
    event_title = reg.event.title if reg.event else "Event"

    verifier_name: Optional[str] = None
    if reg.verified_by:
        verifier_user_res = await db.execute(
            select(User)
            .options(
                selectinload(User.admin_profile),
                selectinload(User.student_profile),
            )
            .filter_by(id=reg.verified_by)
        )
        v_user = verifier_user_res.scalars().first()
        if v_user:
            if v_user.admin_profile:
                verifier_name = v_user.admin_profile.full_name
            elif v_user.student_profile:
                verifier_name = v_user.student_profile.full_name
            else:
                verifier_name = v_user.email

    already_verified = reg.status == RegistrationStatus.VERIFIED

    return VerificationPreviewResponse(
        registration_id=reg.id,
        student_id=reg.student_id,
        student_name=student_name,
        student_photo_url=student_photo,
        branch=branch,
        section=section,
        academic_year=academic_year,
        registration_number=reg.registration_number,
        event_id=reg.event_id,
        event_title=event_title,
        status=reg.status,
        registered_at=reg.registered_at,
        already_verified=already_verified,
        verified_at=reg.verified_at,
        verified_by_name=verifier_name,
        achievement_position=reg.achievement_position,
        computed_certificate_url=reg.computed_certificate_url,
    )


@router.post("/scan", response_model=VerificationPreviewResponse)
async def scan_qr_code(
    body: ScanQRRequest,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    # 1. Parse JSON payload
    try:
        payload_dict = json.loads(body.qr_payload)
        data_dict = payload_dict["data"]
        provided_sig = payload_dict["sig"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_FORMAT: QR payload is invalid or malformed JSON",
        )

    # 2. Recompute HMAC Signature
    raw_data_json = json.dumps(data_dict, sort_keys=True)
    expected_sig = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        raw_data_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]

    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_SIGNATURE: Tampered or unauthentic QR payload detected",
        )

    reg_num = data_dict.get("reg_num")
    event_id_str = data_dict.get("event_id")

    # 3. Query Registration
    query = (
        select(EventRegistration)
        .options(
            selectinload(EventRegistration.student),
            selectinload(EventRegistration.event),
        )
        .filter_by(registration_number=reg_num)
    )
    res = await db.execute(query)
    reg = res.scalars().first()
    if not reg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="REGISTRATION_NOT_FOUND: No registration record matching this QR",
        )

    return await _build_preview_response(reg, db)


@router.post("/confirm", response_model=VerificationPreviewResponse)
async def confirm_verification(
    body: ConfirmVerificationRequest,
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    query = (
        select(EventRegistration)
        .options(
            selectinload(EventRegistration.student),
            selectinload(EventRegistration.event),
        )
        .filter_by(id=body.registration_id)
    )
    res = await db.execute(query)
    reg = res.scalars().first()
    if not reg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registration record not found",
        )

    now_utc = datetime.now(timezone.utc)
    reg.status = RegistrationStatus.VERIFIED
    reg.verified_at = now_utc
    reg.verified_by = current_user.id

    await db.commit()
    await db.refresh(reg)

    preview = await _build_preview_response(reg, db)
    await broadcast_event(
        channel="registrations",
        event_type="registration.verified",
        entity_id=str(reg.id),
        action="verified",
        payload={
            "registration_id": str(reg.id),
            "event_id": str(reg.event_id),
            "verified_at": now_utc.isoformat(),
        },
    )

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="verified",
        entity_type="registration",
        entity_id=reg.id,
        payload={"registration_id": str(reg.id), "event_id": str(reg.event_id)},
    )

    return preview


@router.get("/stats/{event_id}", response_model=VerificationStatsResponse)
async def get_verification_stats(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    tot_res = await db.execute(
        select(func.count(EventRegistration.id)).filter_by(event_id=event_id)
    )
    total_registered = tot_res.scalar() or 0

    ver_res = await db.execute(
        select(func.count(EventRegistration.id)).filter_by(
            event_id=event_id, status=RegistrationStatus.VERIFIED
        )
    )
    total_verified = ver_res.scalar() or 0

    rate = (total_verified / total_registered * 100.0) if total_registered > 0 else 0.0

    return VerificationStatsResponse(
        event_id=event_id,
        total_registered=total_registered,
        total_verified=total_verified,
        verification_rate=round(rate, 2),
    )


@router.get("/manual-search", response_model=List[VerificationPreviewResponse])
async def manual_search_registrations(
    event_id: uuid.UUID = Query(...),
    query: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session),
):
    q_str = f"%{query.strip().lower()}%"
    stmt = (
        select(EventRegistration)
        .join(StudentProfile, EventRegistration.student_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .options(
            selectinload(EventRegistration.student),
            selectinload(EventRegistration.event),
        )
        .filter(
            EventRegistration.event_id == event_id,
            or_(
                func.lower(EventRegistration.registration_number).like(q_str),
                func.lower(StudentProfile.full_name).like(q_str),
                func.lower(User.email).like(q_str),
            ),
        )
    )

    res = await db.execute(stmt)
    registrations = res.scalars().all()

    previews = []
    for r in registrations:
        previews.append(await _build_preview_response(r, db))

    return previews
