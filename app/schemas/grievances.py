import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import GrievanceStatus, GrievanceCategory


class GrievanceCreate(BaseModel):
    subject: str = Field(..., min_length=2)
    message: str = Field(..., min_length=5)
    category: GrievanceCategory = GrievanceCategory.OTHER
    is_anonymous: bool = False


class GrievanceUpdate(BaseModel):
    status: Optional[GrievanceStatus] = None
    admin_response: Optional[str] = None


class GrievanceResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    subject: str
    message: str
    category: GrievanceCategory
    is_anonymous: bool
    status: GrievanceStatus
    submitted_at: datetime
    under_review_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    admin_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedGrievancesResponse(BaseModel):
    items: List[GrievanceResponse]
    total: int
    limit: int
    offset: int
