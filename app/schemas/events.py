import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import EventCategory


class EventCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=5)
    category: EventCategory
    event_date: datetime
    event_year: int
    location: str
    banner_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    registration_deadline: datetime
    is_active: bool = True
    certificate_url_pattern: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    category: Optional[EventCategory] = None
    event_date: Optional[datetime] = None
    event_year: Optional[int] = None
    location: Optional[str] = None
    banner_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    registration_deadline: Optional[datetime] = None
    is_active: Optional[bool] = None
    certificate_url_pattern: Optional[str] = None


class EventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    category: EventCategory
    event_date: datetime
    event_year: int
    location: str
    banner_image_url: Optional[str] = None
    max_participants: Optional[int] = None
    registration_deadline: datetime
    certificate_url_pattern: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedEventsResponse(BaseModel):
    items: List[EventResponse]
    total: int
    limit: int
    offset: int
