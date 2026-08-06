from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.deps import require_role
from app.models.user import StudentProfile, User
from app.schemas.auth import OnboardingStudentRequest, StudentProfileResponse

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.post(
    "/student",
    response_model=StudentProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def onboard_student(
    body: OnboardingStudentRequest,
    force: bool = Query(False, description="Force update profile even if onboarding is already completed"),
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(StudentProfile).filter_by(user_id=current_user.id)
    res = await db.execute(query)
    profile = res.scalars().first()

    if not profile:
        profile = StudentProfile(
            user_id=current_user.id,
            full_name=current_user.email.split("@")[0].capitalize(),
            branch=body.branch,
            section=body.section,
            phone_number=body.phone_number,
            academic_year=body.academic_year,
        )
        db.add(profile)

    if profile.onboarding_completed and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding already completed. Pass force=true to update profile.",
        )

    profile.branch = body.branch
    profile.section = body.section
    profile.phone_number = body.phone_number
    profile.academic_year = body.academic_year
    profile.cgpa = body.cgpa
    profile.linkedin_url = body.linkedin_url
    profile.github_url = body.github_url
    profile.instagram_url = body.instagram_url
    if body.profile_photo_url is not None:
        profile.profile_photo_url = body.profile_photo_url
    profile.onboarding_completed = True

    # User is no longer on first login after onboarding
    user_query = select(User).filter_by(id=current_user.id)
    u_res = await db.execute(user_query)
    user_obj = u_res.scalars().first()
    if user_obj:
        user_obj.is_first_login = False

    await db.commit()
    await db.refresh(profile)

    return profile
