import asyncio
import uuid
import sys
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models.user import User, StudentProfile
from app.models.enums import UserRole
from app.models.event import Event, EventRegistration
from app.models.enums import EventCategory, RegistrationStatus
from app.core.security import get_password_hash

async def add_sample():
    async with AsyncSessionLocal() as session:
        # Check if student exists
        res = await session.execute(select(User).where(User.email == "student3@example.com"))
        student_row = res.scalars().first()
        
        student_id = uuid.uuid4()
        if not student_row:
            print("Creating sample student...")
            session.add(User(
                id=student_id,
                email="student3@example.com",
                hashed_password=get_password_hash("password123"),
                role=UserRole.STUDENT,
                is_active=True,
                is_first_login=False,
                created_at=datetime.now(timezone.utc)
            ))
            session.add(StudentProfile(
                user_id=student_id,
                full_name="John Doe",
                phone_number="1234567890",
                branch="CS",
                section="A",
                academic_year="Year 3",
                onboarding_completed=True,
                created_at=datetime.now(timezone.utc)
            ))
            await session.commit()
        else:
            student_id = student_row.id
            print("Student already exists.")

        # Check if we have an active upcoming event
        res = await session.execute(select(Event).where(Event.category == EventCategory.UPCOMING))
        event_row = res.scalars().first()
        
        event_id = uuid.uuid4()
        if not event_row:
            print("Creating sample upcoming event...")
            session.add(Event(
                id=event_id,
                title="Sample Hackathon 2026",
                description="A hackathon for testing registrations.",
                event_date=datetime.now(timezone.utc) + timedelta(days=2),
                location="Main Auditorium",
                category=EventCategory.UPCOMING,
                max_participants=100,
                registration_deadline=datetime.now(timezone.utc) + timedelta(days=1),
                created_at=datetime.now(timezone.utc)
            ))
            await session.commit()
        else:
            event_id = event_row.id
            print(f"Using existing upcoming event.")

        # Check if registration exists
        res = await session.execute(select(EventRegistration).where(
            EventRegistration.student_id == student_id,
            EventRegistration.event_id == event_id
        ))
        reg_row = res.scalars().first()
        
        reg_id = uuid.uuid4()
        if not reg_row:
            print("Creating sample registration...")
            reg_number = f"REG-{secrets.token_hex(4).upper()}"
            session.add(EventRegistration(
                id=reg_id,
                student_id=student_id,
                event_id=event_id,
                registration_number=reg_number,
                qr_code_data=str(reg_id),
                status=RegistrationStatus.PENDING,
                registered_at=datetime.now(timezone.utc)
            ))
            await session.commit()
            
            print(f"\n==========================================")
            print(f"SUCCESS! Registration created.")
            print(f"Student Login: student3@example.com / password123")
            print(f"Event ID: {event_id}")
            print(f"QR Payload (for manual testing via API or QR generator): {reg_id}")
            print(f"==========================================\n")
        else:
            print(f"\n==========================================")
            print(f"Registration already exists!")
            print(f"Student Login: student3@example.com / password123")
            print(f"Event ID: {event_id}")
            print(f"QR Payload: {reg_row.qr_code_data}")
            print(f"==========================================\n")

if __name__ == "__main__":
    asyncio.run(add_sample())
