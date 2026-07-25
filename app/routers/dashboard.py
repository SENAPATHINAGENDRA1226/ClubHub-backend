from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_async_session
from app.core.deps import get_current_user, require_role
from app.models.committee import Committee
from app.models.content import Alumni
from app.models.enums import UserRole
from app.models.event import Event, EventRegistration
from app.models.user import StudentProfile, User
from app.schemas.dashboard import (
    AdminDashboardResponse,
    BarChartPoint,
    StudentDashboardResponse,
    TimeSeriesPoint,
)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboards"])


@router.get("/student", response_model=StudentDashboardResponse)
async def get_student_dashboard(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    # Total Active Events
    events_res = await db.execute(select(func.count(Event.id)).filter_by(is_active=True))
    total_events = events_res.scalar() or 0

    # Total Active Student Profiles
    members_res = await db.execute(select(func.count(StudentProfile.id)))
    active_members_count = members_res.scalar() or 0

    # Total Committees
    comm_res = await db.execute(select(func.count(Committee.id)))
    active_committees_count = comm_res.scalar() or 0

    # Current Student Registrations Count
    my_registrations_count = 0
    if current_user and current_user.role == UserRole.STUDENT:
        sp_res = await db.execute(select(StudentProfile).filter_by(user_id=current_user.id))
        sp = sp_res.scalars().first()
        if sp:
            reg_res = await db.execute(
                select(func.count(EventRegistration.id)).filter_by(student_id=sp.id)
            )
            my_registrations_count = reg_res.scalar() or 0

    quick_links = [
        {"title": "Explore Events", "url": "/events", "icon": "calendar"},
        {"title": "My Registrations", "url": "/profile/registrations", "icon": "ticket"},
        {"title": "Certificates", "url": "/profile/certificates", "icon": "award"},
        {"title": "Committees", "url": "/committees", "icon": "users"},
    ]

    return StudentDashboardResponse(
        total_events=total_events,
        active_members_count=active_members_count,
        active_committees_count=active_committees_count,
        my_registrations_count=my_registrations_count,
        quick_links=quick_links,
    )


@router.get("/admin", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    current_user: User = Depends(require_role("admin", "committee")),
    db: AsyncSession = Depends(get_async_session),
):
    now_utc = datetime.now(timezone.utc)

    # 1. Total Events
    tot_events_res = await db.execute(select(func.count(Event.id)))
    total_events = tot_events_res.scalar() or 0

    # 2. Total Student Members
    tot_members_res = await db.execute(select(func.count(User.id)).filter(User.role == UserRole.STUDENT))
    total_members = tot_members_res.scalar() or 0

    # 3. Total Alumni
    tot_alumni_res = await db.execute(select(func.count(Alumni.id)))
    total_alumni = tot_alumni_res.scalar() or 0

    # 4. Upcoming Events Count
    up_events_res = await db.execute(
        select(func.count(Event.id)).filter(Event.event_date >= now_utc, Event.is_active == True)
    )
    upcoming_events_count = up_events_res.scalar() or 0

    # 5. Registrations Over Time (Grouped by Month for Recharts line chart)
    # Using date_trunc for PostgreSQL
    time_series_query = (
        select(
            func.to_char(EventRegistration.registered_at, "Mon YYYY").label("month_str"),
            func.count(EventRegistration.id).label("reg_count"),
            func.date_trunc("month", EventRegistration.registered_at).label("month_date"),
        )
        .group_by("month_str", "month_date")
        .order_by("month_date")
    )
    ts_res = await db.execute(time_series_query)
    ts_rows = ts_res.all()

    registrations_over_time: List[TimeSeriesPoint] = []
    for r in ts_rows:
        registrations_over_time.append(TimeSeriesPoint(month=r[0], value=r[1]))

    # Fallback default point if empty dataset
    if not registrations_over_time:
        registrations_over_time.append(TimeSeriesPoint(month=now_utc.strftime("%b %Y"), value=0))

    # 6. Most Popular Events (Top 4 events by registration count for Recharts horizontal bar chart)
    pop_query = (
        select(
            Event.title.label("title"),
            func.count(EventRegistration.id).label("reg_count"),
        )
        .join(EventRegistration, EventRegistration.event_id == Event.id, isouter=True)
        .group_by(Event.id, Event.title)
        .order_by(func.count(EventRegistration.id).desc())
        .limit(4)
    )
    pop_res = await db.execute(pop_query)
    pop_rows = pop_res.all()

    most_popular_events: List[BarChartPoint] = []
    for row in pop_rows:
        most_popular_events.append(BarChartPoint(label=row[0], value=row[1]))

    return AdminDashboardResponse(
        total_events=total_events,
        total_members=total_members,
        total_alumni=total_alumni,
        upcoming_events_count=upcoming_events_count,
        registrations_over_time=registrations_over_time,
        most_popular_events=most_popular_events,
    )
