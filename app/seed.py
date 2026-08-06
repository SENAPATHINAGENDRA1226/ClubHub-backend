import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.future import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.committee import Committee
from app.models.enums import (
    CommitteeCategory,
    CommitteeSubCategory,
    EventCategory,
    UserRole,
)
from app.models.event import Event
from app.models.user import AdminProfile, User


async def seed_data():
    async with AsyncSessionLocal() as session:
        # 1. Seed Admin User
        result = await session.execute(select(User).filter_by(email="admin@csmd-dlides-club.com"))
        admin_user = result.scalars().first()

        if not admin_user:
            admin_user = User(
                email="admin@csmd-dlides-club.com",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
                is_first_login=False,
            )
            session.add(admin_user)
            await session.flush()

            admin_profile = AdminProfile(
                user_id=admin_user.id,
                full_name="System Administrator",
                designation="Chief Administrator",
            )
            session.add(admin_profile)
            print("Seeded Admin User: admin@csmd-dlides-club.com (password: admin123)")

        # 2. Seed Committees ONLY if database has 0 committees
        comm_count_res = await session.execute(select(func.count(Committee.id)))
        if (comm_count_res.scalar() or 0) == 0:
            committees_data = [
                {
                    "name": "CSM Faculty Board",
                    "category": CommitteeCategory.FACULTY,
                    "sub_category": CommitteeSubCategory.CSM,
                    "description": "Computer Science & Machine Learning Departmental Faculty Committee",
                },
                {
                    "name": "Coding Club Committee",
                    "category": CommitteeCategory.STUDENT,
                    "sub_category": CommitteeSubCategory.CODING,
                    "description": "Student Competitive Programming & Full Stack Development Club",
                },
                {
                    "name": "Campus Sports Committee",
                    "category": CommitteeCategory.STUDENT,
                    "sub_category": CommitteeSubCategory.SPORTS,
                    "description": "Annual Campus Athletics & Inter-College Tournament Committee",
                },
            ]
            for c_data in committees_data:
                committee = Committee(**c_data)
                session.add(committee)
                print(f"Seeded Committee: {c_data['name']}")

        # 3. Seed Sample Events ONLY if database has 0 events
        event_count_res = await session.execute(select(func.count(Event.id)))
        if (event_count_res.scalar() or 0) == 0:
            events_data = [
                {
                    "title": "Hackathon 2026: AI & Cloud Solutions",
                    "description": "48-hour hackathon for building modern AI & cloud-native web applications.",
                    "category": EventCategory.UPCOMING,
                    "event_date": datetime.now(timezone.utc) + timedelta(days=14),
                    "event_year": 2026,
                    "location": "Main Auditorium & Virtual Labs",
                    "max_participants": 200,
                    "registration_deadline": datetime.now(timezone.utc) + timedelta(days=10),
                    "created_by": admin_user.id,
                    "is_active": True,
                },
                {
                    "title": "Annual Coding Bootcamp 2026",
                    "description": "Live interactive algorithms & system design workshop series.",
                    "category": EventCategory.CURRENT,
                    "event_date": datetime.now(timezone.utc),
                    "event_year": 2026,
                    "location": "Lab 3 & Zoom",
                    "max_participants": 100,
                    "registration_deadline": datetime.now(timezone.utc),
                    "created_by": admin_user.id,
                    "is_active": True,
                },
                {
                    "title": "Winter CodeFest 2025",
                    "description": "Annual winter competitive programming contest.",
                    "category": EventCategory.PAST,
                    "event_date": datetime(2025, 12, 15, 10, 0, tzinfo=timezone.utc),
                    "event_year": 2025,
                    "location": "Computer Science Block",
                    "max_participants": 150,
                    "registration_deadline": datetime(2025, 12, 10, 23, 59, tzinfo=timezone.utc),
                    "created_by": admin_user.id,
                    "is_active": True,
                },
            ]
            for e_data in events_data:
                event = Event(**e_data)
                session.add(event)
                print(f"Seeded Event: {e_data['title']}")

        await session.commit()
        print("Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
