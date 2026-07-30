import io
import os
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import get_current_user, require_role
from app.models.content import Certificate
from app.models.enums import CertificateType
from app.models.event import Event, EventRegistration
from app.models.user import StudentProfile, User
from app.schemas.certificates import (
    CertificateCreate,
    CertificateResponse,
    PaginatedCertificatesResponse,
)
from app.services.pdf import generate_certificate_pdf
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


@router.get("/me", response_model=PaginatedCertificatesResponse)
async def get_my_certificates(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
    student_profile = sp_res.scalars().first()
    if not student_profile:
        return PaginatedCertificatesResponse(items=[], total=0, limit=limit, offset=offset)

    query = (
        select(Certificate)
        .options(selectinload(Certificate.event))
        .filter_by(student_id=student_profile.id)
        .order_by(Certificate.issued_at.desc())
    )
    count_query = select(func.count(Certificate.id)).filter_by(student_id=student_profile.id)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    certificates = res.scalars().all()

    return PaginatedCertificatesResponse(
        items=[CertificateResponse.model_validate(c) for c in certificates],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("", response_model=PaginatedCertificatesResponse)
async def list_certificates(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    query = (
        select(Certificate)
        .options(selectinload(Certificate.event))
        .order_by(Certificate.issued_at.desc())
    )
    count_query = select(func.count(Certificate.id))

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    certificates = res.scalars().all()

    return PaginatedCertificatesResponse(
        items=[CertificateResponse.model_validate(c) for c in certificates],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    body: CertificateCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    sp_res = await db.execute(
        select(StudentProfile).filter(
            or_(StudentProfile.id == body.student_id, StudentProfile.user_id == body.student_id)
        )
    )
    student_profile = sp_res.scalars().first()
    if not student_profile:
        u_res = await db.execute(select(User).filter_by(id=body.student_id))
        user_obj = u_res.scalars().first()
        if user_obj:
            student_profile = StudentProfile(
                id=uuid.uuid4(),
                user_id=user_obj.id,
                full_name=user_obj.email.split("@")[0].capitalize(),
                branch="General",
                section="A",
                phone_number="",
                academic_year="2026",
                onboarding_completed=False,
            )
            db.add(student_profile)
            await db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student profile or user not found for ID '{body.student_id}'",
            )

    e_res = await db.execute(select(Event).filter_by(id=body.event_id))
    event = e_res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    now_utc = datetime.now(timezone.utc)
    cert_id = uuid.uuid4()

    if body.file_url and (body.file_url.startswith("http://") or body.file_url.startswith("https://")):
        file_url = body.file_url
    else:
        cert_type_str = body.certificate_type.value if hasattr(body.certificate_type, "value") else str(body.certificate_type)
        file_url = generate_certificate_pdf(
            certificate_id=cert_id,
            student_name=student_profile.full_name,
            event_title=event.title,
            certificate_type=cert_type_str,
            issued_at=now_utc,
        )

    certificate = Certificate(
        id=cert_id,
        student_id=student_profile.id,
        event_id=event.id,
        certificate_type=body.certificate_type,
        file_url=file_url,
        issued_at=now_utc,
    )
    db.add(certificate)
    await db.commit()

    res = await db.execute(
        select(Certificate)
        .options(selectinload(Certificate.event))
        .filter_by(id=cert_id)
    )
    full_cert = res.scalars().first()

    cert_data = CertificateResponse.model_validate(full_cert).model_dump(mode="json")

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="certificate",
        entity_id=full_cert.id,
        payload={"event_id": str(body.event_id), "student_id": str(body.student_id)},
    )

    await broadcast(
        channel="certificates",
        event_type="certificates.manual.created",
        entity_id=str(full_cert.id),
        action="created",
        payload=cert_data,
    )

    return full_cert


@router.get("/{certificate_id}/download")
async def download_certificate(
    certificate_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Certificate).filter_by(id=certificate_id))
    cert = res.scalars().first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate record not found",
        )

    if cert.file_url.startswith("http://") or cert.file_url.startswith("https://"):
        return RedirectResponse(url=cert.file_url)

    media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "certificates")
    file_path = os.path.join(media_dir, f"{cert.id}.pdf")

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate PDF file not found on disk",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate_{cert.id}.pdf",
    )


@router.post("/bulk-upload", status_code=status.HTTP_200_OK)
async def bulk_upload_certificates(
    event_id: uuid.UUID = Form(...),
    certificate_type: CertificateType = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .zip archive",
        )

    e_res = await db.execute(select(Event).filter_by(id=event_id))
    event = e_res.scalars().first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    content = await file.read()
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open zip file: {str(e)}",
        )

    media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "certificates")
    os.makedirs(media_dir, exist_ok=True)

    pdf_entries = [f for f in z.namelist() if f.lower().endswith(".pdf") and not f.startswith("__MACOSX")]
    matched_count = 0
    unmatched_files = []
    now_utc = datetime.now(timezone.utc)

    for entry_path in pdf_entries:
        filename = os.path.basename(entry_path)
        base_name = os.path.splitext(filename)[0].strip()

        matched_student_id: Optional[uuid.UUID] = None

        # Strategy 1: Match by Registration Number
        reg_res = await db.execute(
            select(EventRegistration).filter(
                EventRegistration.event_id == event_id,
                func.lower(EventRegistration.registration_number) == base_name.lower(),
            )
        )
        reg = reg_res.scalars().first()
        if reg:
            matched_student_id = reg.student_id
        else:
            # Strategy 2: Match by Student Email
            user_res = await db.execute(
                select(User)
                .options(selectinload(User.student_profile))
                .filter(func.lower(User.email) == base_name.lower())
            )
            user = user_res.scalars().first()
            if user and user.student_profile:
                matched_student_id = user.student_profile.id

        if matched_student_id:
            pdf_bytes = z.read(entry_path)
            # Check existing certificate
            cert_res = await db.execute(
                select(Certificate).filter_by(
                    student_id=matched_student_id,
                    event_id=event_id,
                    certificate_type=certificate_type,
                )
            )
            existing_cert = cert_res.scalars().first()

            if existing_cert:
                cert_id = existing_cert.id
                existing_cert.issued_at = now_utc
            else:
                cert_id = uuid.uuid4()
                file_url = f"/media/certificates/{cert_id}.pdf"
                new_cert = Certificate(
                    id=cert_id,
                    student_id=matched_student_id,
                    event_id=event_id,
                    certificate_type=certificate_type,
                    file_url=file_url,
                    issued_at=now_utc,
                )
                db.add(new_cert)

            out_path = os.path.join(media_dir, f"{cert_id}.pdf")
            with open(out_path, "wb") as f_out:
                f_out.write(pdf_bytes)

            matched_count += 1
        else:
            unmatched_files.append(filename)

    await db.commit()

    if matched_count > 0:
        await write_audit_log(
            db,
            actor_user_id=current_user.id,
            action="created",
            entity_type="certificate",
            payload={"event_id": str(event_id), "bulk_matched": matched_count},
        )

        await broadcast(
            channel="certificates",
            event_type="certificates.bulk.created",
            entity_id=str(event_id),
            action="created",
            payload={"event_id": str(event_id), "matched_count": matched_count},
        )

    return {
        "total_files": len(pdf_entries),
        "matched_count": matched_count,
        "unmatched_files": unmatched_files,
    }


@router.delete("/{certificate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate(
    certificate_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(select(Certificate).filter_by(id=certificate_id))
    cert = res.scalars().first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "certificates")
    file_path = os.path.join(media_dir, f"{cert.id}.pdf")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    c_id_str = str(cert.id)
    await db.delete(cert)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="certificate",
        payload={"certificate_id": c_id_str},
    )

    await broadcast(
        channel="certificates",
        event_type="certificates.manual.deleted",
        entity_id=c_id_str,
        action="deleted",
        payload={"certificate_id": c_id_str},
    )

    return None
