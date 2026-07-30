import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SiteSettingResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SiteSettingUpdate(BaseModel):
    value: Dict[str, Any]


class ClubProfileValue(BaseModel):
    club_name: str = "ClubHub"
    tagline: str = "Where builders meet."
    logo_url: Optional[str] = None
    footer_text: str = "© 2026 ClubHub. All rights reserved."


class AcademicConfigValue(BaseModel):
    branches: List[str] = ["CSE", "CSM", "CSD", "ECE", "EEE", "ME", "CE"]
    sections: List[str] = ["A", "B", "C", "D"]
    academic_years: List[str] = ["1st Year", "2nd Year", "3rd Year", "4th Year"]


class NotificationPrefsValue(BaseModel):
    new_event: bool = True
    new_opportunity: bool = True
    grievance_resolved: bool = True
    new_resource: bool = True
    certificate_issued: bool = True
    alumni_added: bool = False


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    entity_type: str
    entity_id: Optional[uuid.UUID] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedAuditLogResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
