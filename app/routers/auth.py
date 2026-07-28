from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.committee import CommitteeAdmin
from app.models.misc import RevokedToken
from app.models.user import AdminProfile, StudentProfile, User
from app.models.enums import UserRole
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    StudentProfileResponse,
    StudentSignupRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/student/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def student_signup(
    signup_data: StudentSignupRequest,
    db: AsyncSession = Depends(get_async_session),
):
    # Check email uniqueness
    res = await db.execute(select(User).filter_by(email=signup_data.email))
    if res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = User(
        email=signup_data.email,
        hashed_password=get_password_hash(signup_data.password),
        role=UserRole.STUDENT,
        is_active=True,
        is_first_login=True,
    )
    db.add(user)
    await db.flush()

    student_profile = StudentProfile(
        user_id=user.id,
        full_name=signup_data.name,
        branch="",
        section="",
        phone_number="",
        academic_year="",
        onboarding_completed=False,
    )
    db.add(student_profile)
    await db.commit()

    access_token = create_access_token(subject=user.id, role=UserRole.STUDENT.value)
    refresh_token = create_refresh_token(subject=user.id, role=UserRole.STUDENT.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        role=UserRole.STUDENT,
        is_first_login=user.is_first_login,
        onboarding_completed=student_profile.onboarding_completed,
    )


@router.post("/student/login", response_model=TokenResponse)
async def student_login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
):
    clean_email = login_data.email.strip().lower()
    query = select(User).options(selectinload(User.student_profile)).filter(func.lower(User.email) == clean_email)
    res = await db.execute(query)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ACCOUNT_NOT_FOUND",
        )

    if user.role != UserRole.STUDENT or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    onboarding_completed = False
    if user.student_profile:
        onboarding_completed = user.student_profile.onboarding_completed

    access_token = create_access_token(subject=user.id, role=UserRole.STUDENT.value)
    refresh_token = create_refresh_token(subject=user.id, role=UserRole.STUDENT.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        role=UserRole.STUDENT,
        is_first_login=user.is_first_login,
        onboarding_completed=onboarding_completed,
    )


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
):
    clean_email = login_data.email.strip().lower()
    query = select(User).options(selectinload(User.admin_profile)).filter(func.lower(User.email) == clean_email)
    res = await db.execute(query)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ACCOUNT_NOT_FOUND",
        )

    if user.role != UserRole.ADMIN or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(subject=user.id, role=UserRole.ADMIN.value)
    refresh_token = create_refresh_token(subject=user.id, role=UserRole.ADMIN.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        role=UserRole.ADMIN,
        is_first_login=user.is_first_login,
        onboarding_completed=True,
    )


@router.post("/committee/login", response_model=TokenResponse)
async def committee_login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
):
    clean_email = login_data.email.strip().lower()
    query = select(User).filter(func.lower(User.email) == clean_email)
    res = await db.execute(query)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ACCOUNT_NOT_FOUND",
        )

    if user.role != UserRole.COMMITTEE or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    ca_res = await db.execute(select(CommitteeAdmin.committee_id).filter_by(user_id=user.id))
    committee_ids = [c for c in ca_res.scalars().all()]

    access_token = create_access_token(
        subject=user.id,
        role=UserRole.COMMITTEE.value,
        committee_ids=[str(c) for c in committee_ids],
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        role=UserRole.COMMITTEE.value,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        role=UserRole.COMMITTEE,
        is_first_login=user.is_first_login,
        onboarding_completed=True,
        committee_ids=committee_ids,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_async_session),
):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    jti = payload.get("jti")
    if jti:
        rev_res = await db.execute(select(RevokedToken).filter_by(jti=jti))
        if rev_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

    user_id = payload.get("sub")
    res = await db.execute(
        select(User)
        .options(selectinload(User.student_profile))
        .filter_by(id=user_id)
    )
    user = res.scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Invalidate old refresh token
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
    if jti:
        db.add(RevokedToken(jti=jti, token_type="refresh", expires_at=expires_at))

    committee_ids = None
    if user.role == UserRole.COMMITTEE:
        ca_res = await db.execute(select(CommitteeAdmin.committee_id).filter_by(user_id=user.id))
        committee_ids = [c for c in ca_res.scalars().all()]

    onboarding_completed = False
    if user.student_profile:
        onboarding_completed = user.student_profile.onboarding_completed
    elif user.role in (UserRole.ADMIN, UserRole.COMMITTEE):
        onboarding_completed = True

    new_access_token = create_access_token(
        subject=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        committee_ids=[str(c) for c in committee_ids] if committee_ids else None,
    )
    new_refresh_token = create_refresh_token(
        subject=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
    )
    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        is_first_login=user.is_first_login,
        onboarding_completed=onboarding_completed,
        committee_ids=committee_ids,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_async_session),
):
    payload = decode_token(body.refresh_token)
    if payload and payload.get("type") == "refresh":
        jti = payload.get("jti")
        if jti:
            rev_res = await db.execute(select(RevokedToken).filter_by(jti=jti))
            if not rev_res.scalars().first():
                exp = payload.get("exp")
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
                db.add(RevokedToken(jti=jti, token_type="refresh", expires_at=expires_at))
                await db.commit()

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_current_user_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    Optional = None
    profile_dict: Optional[Dict[str, Any]] = None
    onboarding_completed = False
    committee_ids = None

    if current_user.role == UserRole.STUDENT and current_user.student_profile:
        onboarding_completed = current_user.student_profile.onboarding_completed
        profile_dict = StudentProfileResponse.model_validate(current_user.student_profile).model_dump(mode="json")
    elif current_user.role == UserRole.ADMIN and current_user.admin_profile:
        onboarding_completed = True
        profile_dict = {
            "id": str(current_user.admin_profile.id),
            "full_name": current_user.admin_profile.full_name,
            "designation": current_user.admin_profile.designation,
            "profile_photo_url": current_user.admin_profile.profile_photo_url,
        }
    elif current_user.role == UserRole.COMMITTEE:
        onboarding_completed = True
        ca_res = await db.execute(select(CommitteeAdmin.committee_id).filter_by(user_id=current_user.id))
        committee_ids = [c for c in ca_res.scalars().all()]

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_first_login=current_user.is_first_login,
        onboarding_completed=onboarding_completed,
        profile=profile_dict,
        committee_ids=committee_ids,
    )
