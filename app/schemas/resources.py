import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ResourceCreate(BaseModel):
    title: str = Field(..., min_length=2)
    description: str
    resource_url: str
    category: str


class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    resource_url: Optional[str] = None
    category: Optional[str] = None


class ResourceResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    resource_url: str
    category: str
    added_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedResourcesResponse(BaseModel):
    items: List[ResourceResponse]
    total: int
    limit: int
    offset: int
