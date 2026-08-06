import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.enums import CertificateType
from app.schemas.events import EventResponse


class CertificateCreate(BaseModel):
    student_id: str
    event_id: uuid.UUID
    certificate_type: CertificateType
    file_url: Optional[str] = None


class CertificateResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    event_id: uuid.UUID
    certificate_type: CertificateType
    file_url: str
    issued_at: datetime
    created_at: datetime
    updated_at: datetime
    event: Optional[EventResponse] = None

    class Config:
        from_attributes = True


class PaginatedCertificatesResponse(BaseModel):
    items: List[CertificateResponse]
    total: int
    limit: int
    offset: int
