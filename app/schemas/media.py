import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import MediaItemType


class MediaItemCreate(BaseModel):
    title: str = Field(..., min_length=2)
    type: MediaItemType
    file_url: str
    cover_image_url: Optional[str] = None
    published_date: datetime


class MediaItemUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[MediaItemType] = None
    file_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    published_date: Optional[datetime] = None


class MediaItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    type: MediaItemType
    file_url: str
    cover_image_url: Optional[str] = None
    published_date: datetime
    uploaded_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedMediaItemsResponse(BaseModel):
    items: List[MediaItemResponse]
    total: int
    limit: int
    offset: int
