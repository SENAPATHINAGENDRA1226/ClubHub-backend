import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.enums import OpportunityType


class OpportunityCreate(BaseModel):
    title: str = Field(..., min_length=2)
    company_name: str
    description: str
    apply_url: str
    opportunity_type: OpportunityType
    deadline: Optional[datetime] = None


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    description: Optional[str] = None
    apply_url: Optional[str] = None
    opportunity_type: Optional[OpportunityType] = None
    deadline: Optional[datetime] = None


class OpportunityResponse(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    description: str
    apply_url: str
    opportunity_type: OpportunityType
    deadline: Optional[datetime] = None
    posted_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedOpportunitiesResponse(BaseModel):
    items: List[OpportunityResponse]
    total: int
    limit: int
    offset: int
