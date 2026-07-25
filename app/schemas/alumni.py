import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AlumniCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    graduation_year: int
    branch: str
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    photo_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    testimonial: Optional[str] = None
    willing_to_mentor: bool = False


class AlumniUpdate(BaseModel):
    full_name: Optional[str] = None
    graduation_year: Optional[int] = None
    branch: Optional[str] = None
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    photo_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    testimonial: Optional[str] = None
    is_published: Optional[bool] = None
    willing_to_mentor: Optional[bool] = None


class AlumniResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    graduation_year: int
    branch: str
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    photo_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    testimonial: Optional[str] = None
    is_published: bool
    willing_to_mentor: bool
    added_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedAlumniResponse(BaseModel):
    items: List[AlumniResponse]
    total: int
    limit: int
    offset: int

class AlumniInviteResponse(BaseModel):
    invite_url: str

class AlumniPublicCreate(AlumniCreate):
    token: str
