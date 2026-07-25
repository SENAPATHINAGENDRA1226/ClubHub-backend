import asyncio
from datetime import datetime, timezone, timedelta
from app.core.database import AsyncSessionLocal
from app.models.event import Event
from sqlalchemy import update

async def update_deadlines():
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Event).values(
                registration_deadline=datetime.now(timezone.utc) + timedelta(days=7),
                event_date=datetime.now(timezone.utc) + timedelta(days=14),
                category="current"
            )
        )
        await session.commit()
        print('Updated all events to be upcoming with a deadline 7 days from now!')

if __name__ == "__main__":
    asyncio.run(update_deadlines())
