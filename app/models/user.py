import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, Enum as SQLEnum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.committee import CommitteeAdmin


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_first_login: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    student_profile: Mapped[Optional["StudentProfile"]] = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    admin_profile: Mapped[Optional["AdminProfile"]] = relationship("AdminProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    committee_admins: Mapped[list["CommitteeAdmin"]] = relationship("CommitteeAdmin", back_populates="user", cascade="all, delete-orphan")


class StudentProfile(BaseModel):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    section: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    academic_year: Mapped[str] = mapped_column(String, nullable=False)
    cgpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    instagram_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="student_profile")


class AdminProfile(BaseModel):
    __tablename__ = "admin_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    designation: Mapped[str] = mapped_column(String, nullable=False)
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="admin_profile")
