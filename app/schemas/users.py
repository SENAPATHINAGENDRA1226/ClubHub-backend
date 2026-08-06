import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserCreateAdmin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole
    full_name: str = Field(..., min_length=2)
    designation: Optional[str] = None
    committee_ids: Optional[List[uuid.UUID]] = None


class UserUpdateAdmin(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    full_name: Optional[str] = None
    committee_ids: Optional[List[uuid.UUID]] = None
    password: Optional[str] = Field(None, min_length=8)



class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    is_first_login: bool
    profile: Optional[Dict[str, Any]] = None
    committee_ids: Optional[List[uuid.UUID]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedUsersResponse(BaseModel):
    items: List[AdminUserResponse]
    total: int
    limit: int
    offset: int
