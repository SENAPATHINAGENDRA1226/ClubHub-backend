import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from app.core.database import AsyncSessionLocal
from app.models.content import Resource, Opportunity, Alumni, Achievement
from app.models.committee import Committee, CommitteeMember
from app.models.enums import OpportunityType, CommitteeCategory, CommitteeSubCategory, AchievementPosition
from app.models.user import User, UserRole
from app.core.security import get_password_hash

async def seed_data():
    async with AsyncSessionLocal() as session:
        # Check if we have an admin user, if not create one for adding these
        res = await session.execute(User.__table__.select().where(User.email == "admin@clubhub.com"))
        admin_row = res.fetchone()
        
        if not admin_row:
            print("Creating default admin user for seeding...")
            admin_id = uuid.uuid4()
            session.add(User(
                id=admin_id,
                email="admin@clubhub.com",
                password_hash=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
                created_at=datetime.now(timezone.utc)
            ))
            await session.commit()
        else:
            admin_id = admin_row.id

        now = datetime.now(timezone.utc)

        print("Seeding Resources...")
        resources = [
            Resource(
                id=uuid.uuid4(),
                title="freeCodeCamp Web Design",
                description="A comprehensive guide to responsive web design.",
                resource_url="https://www.freecodecamp.org/learn/responsive-web-design/",
                category="Web Dev",
                added_by=admin_id,
                created_at=now
            ),
            Resource(
                id=uuid.uuid4(),
                title="LeetCode Top Interview 150",
                description="Must-do coding questions for technical interviews.",
                resource_url="https://leetcode.com/studyplan/top-interview-150/",
                category="DSA",
                added_by=admin_id,
                created_at=now
            ),
            Resource(
                id=uuid.uuid4(),
                title="Roadmap.sh - AI/ML",
                description="Step by step guide to becoming an Artificial Intelligence and Machine Learning expert.",
                resource_url="https://roadmap.sh/ai-data-scientist",
                category="AI/ML",
                added_by=admin_id,
                created_at=now
            )
        ]
        session.add_all(resources)

        print("Seeding Opportunities...")
        opportunities = [
            Opportunity(
                id=uuid.uuid4(),
                title="Software Engineering Intern (Summer 2027)",
                company_name="Google",
                opportunity_type=OpportunityType.INTERNSHIP,
                description="Join Google as a Software Engineering Intern. Work on core products and services that impact billions of users.",
                apply_url="https://careers.google.com/students/",
                deadline=now + timedelta(days=30),
                posted_by=admin_id,
                created_at=now
            ),
            Opportunity(
                id=uuid.uuid4(),
                title="Global Hackathon 2026",
                company_name="Major League Hacking",
                opportunity_type=OpportunityType.HACKATHON,
                description="Compete with developers around the world to build innovative solutions. Prizes up to $50,000.",
                apply_url="https://mlh.io/",
                deadline=now + timedelta(days=15),
                posted_by=admin_id,
                created_at=now
            )
        ]
        session.add_all(opportunities)

        print("Seeding Committees...")
        committee_1_id = uuid.uuid4()
        csm = Committee(
            id=committee_1_id,
            name="Computer Science & Math (CSM) Faculty Committee",
            description="Overseeing the CSM department curriculum and events.",
            category=CommitteeCategory.FACULTY,
            sub_category=CommitteeSubCategory.CSM
        )
        session.add(csm)

        committee_2_id = uuid.uuid4()
        coding = Committee(
            id=committee_2_id,
            name="Zero One Coding Club",
            description="The premier competitive coding and development club.",
            category=CommitteeCategory.STUDENT,
            sub_category=CommitteeSubCategory.CODING
        )
        session.add(coding)
        
        await session.commit()

        print("Seeding Committee Members...")
        members = [
            CommitteeMember(
                id=uuid.uuid4(),
                committee_id=committee_1_id,
                full_name="Dr. Alan Turing",
                role_title="Head of Department",
                email="alan.t@university.edu",
                photo_url=None,
                bio="Pioneer in theoretical computer science and AI.",
                order_index=1
            ),
            CommitteeMember(
                id=uuid.uuid4(),
                committee_id=committee_2_id,
                full_name="Ada Lovelace",
                role_title="President",
                email="ada@students.edu",
                photo_url=None,
                bio="Leading the club to new heights in algorithmic problem solving.",
                order_index=1
            )
        ]
        session.add_all(members)

        print("Seeding Alumni...")
        alumni = [
            Alumni(
                id=uuid.uuid4(),
                full_name="Grace Hopper",
                graduation_year=2021,
                branch="CS",
                current_company="US Navy Tech",
                linkedin_url="https://linkedin.com",
                testimonial="The coding club was where I built the foundation of my career.",
                photo_url=None,
                added_by=admin_id,
                created_at=now
            )
        ]
        session.add_all(alumni)

        print("Seeding Achievements...")
        achievements = [
            Achievement(
                id=uuid.uuid4(),
                title="First Place - National Hackathon",
                description="Built an AI-driven accessibility tool in 48 hours.",
                year=2025,
                position=AchievementPosition.WINNER,
                event_id=None,
                student_id=None,
                created_at=now
            )
        ]
        session.add_all(achievements)

        await session.commit()
        print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
