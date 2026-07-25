from app.models import StudentProfile
from app.models import User
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import EventCategory, RegistrationStatus, AchievementPosition


class Event(BaseModel):
    __tablename__ = "events"

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[EventCategory] = mapped_column(SQLEnum(EventCategory), index=True, nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    banner_image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    certificate_url_pattern: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    registrations: Mapped[list["EventRegistration"]] = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")
    creator: Mapped[Optional["User"]] = relationship("User")


class EventRegistration(BaseModel):
    __tablename__ = "event_registrations"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    registration_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    qr_code_data: Mapped[str] = mapped_column(Text, nullable=False)
    qr_code_image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[RegistrationStatus] = mapped_column(SQLEnum(RegistrationStatus), default=RegistrationStatus.PENDING, nullable=False)
    achievement_position: Mapped[Optional[AchievementPosition]] = mapped_column(SQLEnum(AchievementPosition), nullable=True)
    certificate_url_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="registrations")
    student: Mapped["StudentProfile"] = relationship("StudentProfile")
    verifier: Mapped[Optional["User"]] = relationship("User")

    @property
    def computed_certificate_url(self) -> Optional[str]:
        if self.certificate_url_override:
            return self.certificate_url_override
        if getattr(self, "event", None) and self.event.certificate_url_pattern:
            return self.event.certificate_url_pattern.replace("{registration_number}", self.registration_number)
        return None
