import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import CommitteeCategory, CommitteeSubCategory


class CommitteeMemberCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    email: Optional[str] = ""
    role_title: str
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    order_index: int = 0
    user_id: Optional[uuid.UUID] = None


class CommitteeMemberUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_title: Optional[str] = None
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    order_index: Optional[int] = None
    user_id: Optional[uuid.UUID] = None


class CommitteeMemberResponse(BaseModel):
    id: uuid.UUID
    committee_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    full_name: str
    email: str
    role_title: str
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommitteeCreate(BaseModel):
    name: str = Field(..., min_length=2)
    category: CommitteeCategory
    sub_category: CommitteeSubCategory
    description: str


class CommitteeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[CommitteeCategory] = None
    sub_category: Optional[CommitteeSubCategory] = None
    description: Optional[str] = None


class CommitteeResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: CommitteeCategory
    sub_category: CommitteeSubCategory
    description: str
    members: Optional[List[CommitteeMemberResponse]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
