import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.enums import RegistrationStatus


class ScanQRRequest(BaseModel):
    qr_payload: str = Field(..., description="Raw JSON string scanned from QR code")


class ConfirmVerificationRequest(BaseModel):
    registration_id: uuid.UUID


class VerificationPreviewResponse(BaseModel):
    registration_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    student_photo_url: Optional[str] = None
    branch: str
    section: str
    academic_year: str
    registration_number: str
    event_id: uuid.UUID
    event_title: str
    status: RegistrationStatus
    registered_at: datetime
    already_verified: bool
    verified_at: Optional[datetime] = None
    verified_by_name: Optional[str] = None
    achievement_position: Optional[str] = None
    computed_certificate_url: Optional[str] = None

    class Config:
        from_attributes = True


class VerificationStatsResponse(BaseModel):
    event_id: uuid.UUID
    total_registered: int
    total_verified: int
    verification_rate: float
