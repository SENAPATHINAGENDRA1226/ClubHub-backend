import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.enums import RegistrationStatus, AchievementPosition
from app.schemas.events import EventResponse


class RegistrationCreate(BaseModel):
    event_id: uuid.UUID


class StudentRegistrationDetail(BaseModel):
    id: uuid.UUID
    full_name: str
    branch: str
    section: str
    phone_number: str
    academic_year: str
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class RegistrationResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    student_id: uuid.UUID
    registration_number: str
    qr_code_data: str
    qr_code_image_url: Optional[str] = None
    status: RegistrationStatus
    achievement_position: Optional[AchievementPosition] = None
    certificate_url_override: Optional[str] = None
    computed_certificate_url: Optional[str] = None
    registered_at: datetime
    verified_at: Optional[datetime] = None
    verified_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    event: Optional[EventResponse] = None
    student: Optional[StudentRegistrationDetail] = None

    class Config:
        from_attributes = True


class PaginatedRegistrationsResponse(BaseModel):
    items: List[RegistrationResponse]
    total: int
    limit: int
    offset: int

class AchievementUpdate(BaseModel):
    achievement_position: AchievementPosition
    certificate_url_override: Optional[str] = None
