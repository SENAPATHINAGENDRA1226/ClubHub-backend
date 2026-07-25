import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import AchievementPosition


class AchievementCreate(BaseModel):
    title: str = Field(..., min_length=2)
    description: str
    position: AchievementPosition
    year: int
    photo_url: Optional[str] = None
    event_id: Optional[uuid.UUID] = None
    student_id: Optional[uuid.UUID] = None


class AchievementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    position: Optional[AchievementPosition] = None
    year: Optional[int] = None
    photo_url: Optional[str] = None
    event_id: Optional[uuid.UUID] = None
    student_id: Optional[uuid.UUID] = None


class AchievementResponse(BaseModel):
    id: uuid.UUID
    event_id: Optional[uuid.UUID] = None
    student_id: Optional[uuid.UUID] = None
    title: str
    description: str
    position: AchievementPosition
    year: int
    photo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedAchievementsResponse(BaseModel):
    items: List[AchievementResponse]
    total: int
    limit: int
    offset: int
