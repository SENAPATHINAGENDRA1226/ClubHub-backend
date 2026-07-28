import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import require_role
from app.core.security import get_password_hash
from app.models.committee import CommitteeAdmin
from app.models.enums import UserRole
from app.models.user import AdminProfile, StudentProfile, User
from app.schemas.users import (
    AdminUserResponse,
    PaginatedUsersResponse,
    UserCreateAdmin,
    UserUpdateAdmin,
)
from app.services.audit import write_audit_log
from app.services.broadcast import broadcast

router = APIRouter(prefix="/api/users", tags=["Admin Manage Users"])


def _build_admin_user_response(user: User, committee_ids: List[uuid.UUID]) -> AdminUserResponse:
    profile_dict = None
    if user.student_profile:
        profile_dict = {
            "full_name": user.student_profile.full_name,
            "branch": user.student_profile.branch,
            "section": user.student_profile.section,
            "phone_number": user.student_profile.phone_number,
            "academic_year": user.student_profile.academic_year,
            "profile_photo_url": user.student_profile.profile_photo_url,
        }
    elif user.admin_profile:
        profile_dict = {
            "full_name": user.admin_profile.full_name,
            "designation": user.admin_profile.designation,
            "profile_photo_url": user.admin_profile.profile_photo_url,
        }

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_first_login=user.is_first_login,
        profile=profile_dict,
        committee_ids=committee_ids,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=PaginatedUsersResponse)
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    query = (
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
    )
    count_query = select(func.count(User.id))

    if role:
        query = query.filter(User.role == role)
        count_query = count_query.filter(User.role == role)

    if search:
        search_filter = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(User.email).like(search_filter))
        count_query = count_query.filter(func.lower(User.email).like(search_filter))

    query = query.order_by(User.created_at.desc())

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    res = await db.execute(query.limit(limit).offset(offset))
    users = res.scalars().all()

    items: List[AdminUserResponse] = []
    for u in users:
        c_ids = [ca.committee_id for ca in u.committee_admins] if u.committee_admins else []
        items.append(_build_admin_user_response(u, c_ids))

    return PaginatedUsersResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_by_admin(
    body: UserCreateAdmin,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    # Check email uniqueness
    dup_res = await db.execute(select(User).filter(func.lower(User.email) == body.email.lower()))
    if dup_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role=body.role,
        is_active=True,
        is_first_login=True,
    )
    db.add(user)
    await db.flush()

    if body.role == UserRole.STUDENT:
        sp = StudentProfile(
            user_id=user.id,
            full_name=body.full_name,
            branch="CSE",
            section="A",
            phone_number="",
            academic_year="1st Year",
            onboarding_completed=False,
        )
        db.add(sp)
    elif body.role == UserRole.ADMIN:
        ap = AdminProfile(
            user_id=user.id,
            full_name=body.full_name,
            designation=body.designation or "System Admin",
        )
        db.add(ap)

    assigned_cids: List[uuid.UUID] = []
    if body.committee_ids:
        for cid in body.committee_ids:
            ca = CommitteeAdmin(user_id=user.id, committee_id=cid)
            db.add(ca)
            assigned_cids.append(cid)

    await db.commit()

    # Re-query user
    q = (
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
        .filter_by(id=user.id)
    )
    full_res = await db.execute(q)
    full_user = full_res.scalars().first()

    response_obj = _build_admin_user_response(full_user, assigned_cids)

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="created",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email, "role": body.role.value},
    )

    await broadcast(
        channel="users",
        event_type="users.created",
        entity_id=str(user.id),
        action="created",
        payload=response_obj.model_dump(mode="json"),
    )

    return response_obj


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user_by_admin(
    user_id: uuid.UUID,
    body: UserUpdateAdmin,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    res = await db.execute(
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
        .filter_by(id=user_id)
    )
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    was_active = user.is_active

    if body.email:
        user.email = body.email
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role:
        user.role = body.role
    if body.password:
        user.hashed_password = get_password_hash(body.password)


    if body.full_name:
        if user.student_profile:
            user.student_profile.full_name = body.full_name
        elif user.admin_profile:
            user.admin_profile.full_name = body.full_name

    if body.committee_ids is not None:
        # Clear existing assignments
        ca_res = await db.execute(select(CommitteeAdmin).filter_by(user_id=user.id))
        for existing_ca in ca_res.scalars().all():
            await db.delete(existing_ca)
        await db.flush()

        # Add new assignments
        for cid in body.committee_ids:
            new_ca = CommitteeAdmin(user_id=user.id, committee_id=cid)
            db.add(new_ca)

    await db.commit()

    # Re-query
    q = (
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
        .filter_by(id=user.id)
    )
    full_res = await db.execute(q)
    full_user = full_res.scalars().first()

    c_ids = [ca.committee_id for ca in full_user.committee_admins] if full_user.committee_admins else []
    response_obj = _build_admin_user_response(full_user, c_ids)

    # Determine action type
    action = "updated"
    if body.is_active is not None and was_active and not body.is_active:
        action = "deactivated"

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action=action,
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email},
    )

    await broadcast(
        channel="users",
        event_type=f"users.{action}",
        entity_id=str(user.id),
        action=action,
        payload=response_obj.model_dump(mode="json"),
    )

    return response_obj


@router.delete("/{user_id}", response_model=AdminUserResponse)
async def delete_user_by_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-deletion is not allowed",
        )

    res = await db.execute(
        select(User)
        .options(
            selectinload(User.student_profile),
            selectinload(User.admin_profile),
            selectinload(User.committee_admins),
        )
        .filter_by(id=user_id)
    )
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts cannot be deleted.",
        )

    c_ids = [ca.committee_id for ca in user.committee_admins] if user.committee_admins else []
    response_data = _build_admin_user_response(user, c_ids).model_dump(mode="json")
    u_id_str = str(user.id)
    u_email = user.email

    await db.delete(user)
    await db.commit()

    await write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="deleted",
        entity_type="user",
        payload={"email": u_email, "user_id": u_id_str},
    )

    await broadcast(
        channel="users",
        event_type="users.deleted",
        entity_id=u_id_str,
        action="deleted",
        payload={"user_id": u_id_str, "email": u_email},
    )

    return AdminUserResponse(**response_data)
