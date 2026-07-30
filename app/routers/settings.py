import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_async_session
from app.core.deps import get_current_user, require_role
from app.models.misc import AuditLog
from app.models.setting import SiteSetting
from app.models.user import AdminProfile, StudentProfile, User
from app.schemas.settings import (
    AuditLogResponse,
    PaginatedAuditLogResponse,
    SiteSettingResponse,
    SiteSettingUpdate,
)
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# ── Defaults for first-run seeding ──────────────────────────────────────────
SETTING_DEFAULTS = {
    "club_profile": {
        "club_name": "ClubHub",
        "tagline": "Where builders meet.",
        "logo_url": None,
        "footer_text": "© 2026 ClubHub. All rights reserved.",
    },
    "academic_config": {
        "branches": ["CSE", "CSM", "CSD", "ECE", "EEE", "ME", "CE"],
        "sections": ["A", "B", "C", "D"],
        "academic_years": ["1st Year", "2nd Year", "3rd Year", "4th Year"],
    },
    "notification_prefs": {
        "new_event": True,
        "new_opportunity": True,
        "grievance_resolved": True,
        "new_resource": True,
        "certificate_issued": True,
        "alumni_added": False,
    },
}


async def _ensure_defaults(db: AsyncSession) -> None:
    """Seed default settings if they don't exist yet."""
    for key, default_value in SETTING_DEFAULTS.items():
        res = await db.execute(select(SiteSetting).filter_by(key=key))
        if not res.scalars().first():
            db.add(SiteSetting(key=key, value=default_value))
    await db.commit()


# ── Public endpoint (no auth) – used by LoginPage/OnboardingPage ───────────
@router.get("/public/{key}", response_model=SiteSettingResponse)
async def get_public_setting(
    key: str,
    db: AsyncSession = Depends(get_async_session),
):
    if key not in ("club_profile", "academic_config", "notification_prefs"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")

    await _ensure_defaults(db)
    res = await db.execute(select(SiteSetting).filter_by(key=key))
    setting = res.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return setting


# ── Admin: list all settings ───────────────────────────────────────────────
@router.get("", response_model=List[SiteSettingResponse])
async def list_settings(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_defaults(db)
    res = await db.execute(select(SiteSetting).order_by(SiteSetting.key))
    return res.scalars().all()


# ── Admin: get single setting ──────────────────────────────────────────────
@router.get("/{key}", response_model=SiteSettingResponse)
async def get_setting(
    key: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_defaults(db)
    res = await db.execute(select(SiteSetting).filter_by(key=key))
    setting = res.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return setting


# ── Admin: update a setting ────────────────────────────────────────────────
@router.put("/{key}", response_model=SiteSettingResponse)
async def update_setting(
    key: str,
    body: SiteSettingUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_defaults(db)
    res = await db.execute(select(SiteSetting).filter_by(key=key))
    setting = res.scalars().first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")

    setting.value = dict(body.value)
    flag_modified(setting, "value")
    await db.commit()
    await db.refresh(setting)

    # Audit
    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="updated",
        entity_type="setting",
        entity_id=setting.id,
        payload={"key": key},
    )

    # Broadcast
    await broadcast(
        channel="settings",
        event_type="settings.updated",
        entity_id=str(setting.id),
        action="updated",
        payload={"key": key, "value": setting.value},
    )

    return setting


# ── Admin: logo upload ─────────────────────────────────────────────────────
@router.post("/logo", response_model=SiteSettingResponse)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    ext = os.path.splitext(file.filename or "logo.png")[1].lower() or ".png"
    allowed_exts = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
    is_img_type = file.content_type and file.content_type.startswith("image/")
    if not is_img_type and ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (.png, .jpg, .jpeg, .webp, .svg)",
        )

    media_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "uploads", "logo"
    )
    os.makedirs(media_dir, exist_ok=True)

    filename = f"club_logo{ext}"
    file_path = os.path.join(media_dir, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logo_url = f"/media/uploads/logo/{filename}"

    # Update club_profile setting
    await _ensure_defaults(db)
    res = await db.execute(select(SiteSetting).filter_by(key="club_profile"))
    setting = res.scalars().first()
    if setting:
        val = dict(setting.value or {})
        val["logo_url"] = logo_url
        setting.value = val
        flag_modified(setting, "value")
        await db.commit()
        await db.refresh(setting)

        await write_audit_log(
            db,
            actor_user_id=current_user.id,
            action="logo_uploaded",
            entity_type="setting",
            entity_id=setting.id,
            payload={"logo_url": logo_url},
        )

        await broadcast(
            channel="settings",
            event_type="settings.updated",
            entity_id=str(setting.id),
            action="updated",
            payload={"key": "club_profile", "value": setting.value},
        )

        return setting

    raise HTTPException(status_code=500, detail="Failed to update club profile")


# ── Admin: audit log (recent admin activity) ───────────────────────────────
@router.get("/audit-log/recent", response_model=PaginatedAuditLogResponse)
async def get_recent_audit_log(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    count_res = await db.execute(select(func.count(AuditLog.id)))
    total = count_res.scalar() or 0

    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(query)
    entries = res.scalars().all()

    items = []
    for e in entries:
        actor_email = None
        actor_name = None
        if e.actor:
            actor_email = e.actor.email
            # Try to get name from profiles
            if hasattr(e.actor, "admin_profile") and e.actor.admin_profile:
                actor_name = e.actor.admin_profile.full_name
            elif hasattr(e.actor, "student_profile") and e.actor.student_profile:
                actor_name = e.actor.student_profile.full_name
            else:
                actor_name = e.actor.email

        items.append(
            AuditLogResponse(
                id=e.id,
                actor_user_id=e.actor_user_id,
                action=e.action,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                payload=e.payload,
                created_at=e.created_at,
                actor_email=actor_email,
                actor_name=actor_name,
            )
        )

    return PaginatedAuditLogResponse(items=items, total=total)
