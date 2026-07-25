import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class ContactMessageCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    subject: str = Field(..., min_length=2)
    message: str = Field(..., min_length=5)


class ContactMessageResponse(BaseModel):
    id: uuid.UUID
    student_id: Optional[uuid.UUID] = None
    name: str
    email: str
    subject: str
    message: str
    submitted_at: datetime
    is_read: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedContactMessagesResponse(BaseModel):
    items: List[ContactMessageResponse]
    total: int
    limit: int
    offset: int
