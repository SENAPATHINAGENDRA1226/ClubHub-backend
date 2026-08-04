from app.models import User
import uuid
from typing import Optional
from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import CommitteeCategory, CommitteeSubCategory


class Committee(BaseModel):
    __tablename__ = "committees"

    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[CommitteeCategory] = mapped_column(SQLEnum(CommitteeCategory), nullable=False)
    sub_category: Mapped[CommitteeSubCategory] = mapped_column(SQLEnum(CommitteeSubCategory), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    members: Mapped[list["CommitteeMember"]] = relationship("CommitteeMember", back_populates="committee", cascade="all, delete-orphan", order_by="CommitteeMember.order_index")
    admins: Mapped[list["CommitteeAdmin"]] = relationship("CommitteeAdmin", back_populates="committee", cascade="all, delete-orphan")


class CommitteeMember(BaseModel):
    __tablename__ = "committee_members"

    committee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("committees.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role_title: Mapped[str] = mapped_column(String, nullable=False)
    faculty_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    committee: Mapped["Committee"] = relationship("Committee", back_populates="members")
    user: Mapped[Optional["User"]] = relationship("User")


class CommitteeAdmin(BaseModel):
    __tablename__ = "committee_admins"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    committee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("committees.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="committee_admins")
    committee: Mapped["Committee"] = relationship("Committee", back_populates="admins")
