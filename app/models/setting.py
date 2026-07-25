from typing import Any, Dict

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SiteSetting(BaseModel):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    value: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
