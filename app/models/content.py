from sqlalchemy.sql.sqltypes import Boolean
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import AchievementPosition, CertificateType, MediaItemType, OpportunityType

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import StudentProfile, User


class Certificate(BaseModel):
    __tablename__ = "certificates"

    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    certificate_type: Mapped[CertificateType] = mapped_column(SQLEnum(CertificateType), nullable=False)
    file_url: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    student: Mapped["StudentProfile"] = relationship("StudentProfile")
    event: Mapped["Event"] = relationship("Event")


class Achievement(BaseModel):
    __tablename__ = "achievements"

    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[AchievementPosition] = mapped_column(SQLEnum(AchievementPosition), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    event: Mapped[Optional["Event"]] = relationship("Event")
    student: Mapped[Optional["StudentProfile"]] = relationship("StudentProfile")


class Alumni(BaseModel):
    __tablename__ = "alumni"

    full_name: Mapped[str] = mapped_column(String, nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    current_company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    testimonial: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    willing_to_mentor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User")


class Resource(BaseModel):
    __tablename__ = "resources"

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resource_url: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User")


class Opportunity(BaseModel):
    __tablename__ = "opportunities"

    title: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str] = mapped_column(String, nullable=False)
    opportunity_type: Mapped[OpportunityType] = mapped_column(SQLEnum(OpportunityType), nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User")


class MediaItem(BaseModel):
    __tablename__ = "media_items"

    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[MediaItemType] = mapped_column(SQLEnum(MediaItemType), nullable=False)
    file_url: Mapped[str] = mapped_column(String, nullable=False)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    published_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    uploader: Mapped[Optional["User"]] = relationship("User")
