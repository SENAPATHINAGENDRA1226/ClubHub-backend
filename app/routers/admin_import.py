import csv
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import require_role
from app.core.security import get_password_hash
from app.models.content import Achievement, Alumni
from app.models.enums import AchievementPosition, EventCategory, UserRole
from app.models.event import Event
from app.models.user import StudentProfile, User

router = APIRouter(prefix="/api/admin/import", tags=["Admin Bulk Data Import"])


async def parse_uploaded_file_rows(file: UploadFile) -> List[Dict[str, Any]]:
    filename = file.filename.lower()
    content = await file.read()
    rows: List[Dict[str, Any]] = []

    if filename.endswith(".csv"):
        text_content = content.decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(io.StringIO(text_content))
        for row in reader:
            cleaned_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            rows.append(cleaned_row)
    elif filename.endswith(".xlsx"):
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        sheet = wb.active
        if not sheet:
            raise HTTPException(status_code=400, detail="Excel sheet is empty")

        headers: List[str] = []
        for cell in sheet[1]:
            val = str(cell.value or "").strip().lower()
            headers.append(val)

        for row_cells in sheet.iter_rows(min_row=2, values_only=True):
            if not any(row_cells):
                continue
            row_dict = {}
            for idx, header in enumerate(headers):
                if header and idx < len(row_cells):
                    val = row_cells[idx]
                    row_dict[header] = str(val).strip() if val is not None else ""
            rows.append(row_dict)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .csv or .xlsx file.",
        )

    return rows


@router.post("/achievements", status_code=status.HTTP_200_OK)
async def import_achievements(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await parse_uploaded_file_rows(file)
    created_count = 0
    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):
        title = row.get("title") or row.get("achievement_title")
        description = row.get("description", "")
        pos_str = (row.get("position") or "winner").lower().replace(" ", "_")
        year_str = row.get("year") or str(datetime.now().year)

        if not title:
            errors.append(f"Row {idx}: Missing title")
            continue

        try:
            year = int(year_str)
        except ValueError:
            year = datetime.now().year

        position_enum = AchievementPosition.WINNER
        if pos_str == "runner_up":
            position_enum = AchievementPosition.RUNNER_UP
        elif pos_str == "special_mention":
            position_enum = AchievementPosition.SPECIAL_MENTION

        student_id: Optional[uuid.UUID] = None
        student_email = row.get("student_email") or row.get("email")
        if student_email:
            u_res = await db.execute(
                select(User)
                .options(selectinload(User.student_profile))
                .filter(func.lower(User.email) == student_email.lower())
            )
            user = u_res.scalars().first()
            if user and user.student_profile:
                student_id = user.student_profile.id

        event_id: Optional[uuid.UUID] = None
        event_title = row.get("event_title") or row.get("event")
        if event_title:
            e_res = await db.execute(select(Event).filter(func.lower(Event.title) == event_title.lower()))
            event_obj = e_res.scalars().first()
            if event_obj:
                event_id = event_obj.id

        achievement = Achievement(
            title=title,
            description=description,
            position=position_enum,
            year=year,
            student_id=student_id,
            event_id=event_id,
            photo_url=row.get("photo_url") or None,
        )
        db.add(achievement)
        created_count += 1

    await db.commit()
    return {
        "imported_count": created_count,
        "error_count": len(errors),
        "errors": errors,
    }


@router.post("/alumni", status_code=status.HTTP_200_OK)
async def import_alumni(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await parse_uploaded_file_rows(file)
    created_count = 0
    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):
        full_name = row.get("full_name") or row.get("name")
        grad_year_str = row.get("graduation_year") or row.get("grad_year") or row.get("year")
        branch = row.get("branch") or "CSE"

        if not full_name or not grad_year_str:
            errors.append(f"Row {idx}: Missing full_name or graduation_year")
            continue

        try:
            grad_year = int(grad_year_str)
        except ValueError:
            errors.append(f"Row {idx}: Invalid graduation_year '{grad_year_str}'")
            continue

        alumni_entry = Alumni(
            full_name=full_name,
            graduation_year=grad_year,
            branch=branch,
            current_company=row.get("current_company") or row.get("company") or None,
            current_role=row.get("current_role") or row.get("role") or None,
            photo_url=row.get("photo_url") or None,
            linkedin_url=row.get("linkedin_url") or row.get("linkedin") or None,
            testimonial=row.get("testimonial") or None,
            added_by=current_user.id,
        )
        db.add(alumni_entry)
        created_count += 1

    await db.commit()
    return {
        "imported_count": created_count,
        "error_count": len(errors),
        "errors": errors,
    }


@router.post("/past-events", status_code=status.HTTP_200_OK)
async def import_past_events(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await parse_uploaded_file_rows(file)
    created_count = 0
    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):
        title = row.get("title") or row.get("event_title")
        description = row.get("description") or "Past Campus Event"
        year_str = row.get("event_year") or row.get("year") or "2025"
        date_str = row.get("event_date") or row.get("date")
        location = row.get("location") or "Campus Main Ground"

        if not title:
            errors.append(f"Row {idx}: Missing event title")
            continue

        try:
            year = int(year_str)
        except ValueError:
            year = 2025

        if date_str:
            try:
                event_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                event_date = datetime(year, 1, 1, 10, 0, tzinfo=timezone.utc)
        else:
            event_date = datetime(year, 1, 1, 10, 0, tzinfo=timezone.utc)

        max_p = None
        if row.get("max_participants"):
            try:
                max_p = int(row["max_participants"])
            except ValueError:
                pass

        event = Event(
            title=title,
            description=description,
            category=EventCategory.PAST,
            event_date=event_date,
            event_year=year,
            location=location,
            banner_image_url=row.get("banner_image_url") or row.get("image_url") or None,
            max_participants=max_p,
            registration_deadline=event_date,
            created_by=current_user.id,
            is_active=True,
        )
        db.add(event)
        created_count += 1

    await db.commit()
    return {
        "imported_count": created_count,
        "error_count": len(errors),
        "errors": errors,
    }


@router.post("/students", status_code=status.HTTP_200_OK)
async def import_students(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await parse_uploaded_file_rows(file)
    created_count = 0
    updated_count = 0
    errors: List[str] = []

    for idx, row in enumerate(rows, start=2):
        email = row.get("email")
        full_name = row.get("full_name") or row.get("name")
        branch = row.get("branch") or "CSE"
        section = row.get("section") or "A"
        phone_number = row.get("phone_number") or row.get("phone") or ""
        academic_year = row.get("academic_year") or row.get("year") or "1st Year"
        cgpa_str = row.get("cgpa")

        if not email or not full_name:
            errors.append(f"Row {idx}: Missing email or full_name")
            continue

        cgpa: Optional[float] = None
        if cgpa_str:
            try:
                cgpa = float(cgpa_str)
            except ValueError:
                pass

        res = await db.execute(
            select(User)
            .options(selectinload(User.student_profile))
            .filter(func.lower(User.email) == email.lower())
        )
        existing_user = res.scalars().first()

        if existing_user:
            if existing_user.student_profile:
                existing_user.student_profile.full_name = full_name
                existing_user.student_profile.branch = branch
                existing_user.student_profile.section = section
                existing_user.student_profile.phone_number = phone_number
                existing_user.student_profile.academic_year = academic_year
                if cgpa is not None:
                    existing_user.student_profile.cgpa = cgpa
                existing_user.student_profile.onboarding_completed = True
                updated_count += 1
            else:
                profile = StudentProfile(
                    user_id=existing_user.id,
                    full_name=full_name,
                    branch=branch,
                    section=section,
                    phone_number=phone_number,
                    academic_year=academic_year,
                    cgpa=cgpa,
                    onboarding_completed=True,
                )
                db.add(profile)
                updated_count += 1
        else:
            new_user = User(
                email=email,
                hashed_password=get_password_hash("Student@123"),
                role=UserRole.STUDENT,
                is_active=True,
                is_first_login=True,
            )
            db.add(new_user)
            await db.flush()

            profile = StudentProfile(
                user_id=new_user.id,
                full_name=full_name,
                branch=branch,
                section=section,
                phone_number=phone_number,
                academic_year=academic_year,
                cgpa=cgpa,
                onboarding_completed=True,
            )
            db.add(profile)
            created_count += 1

    await db.commit()
    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors,
    }
