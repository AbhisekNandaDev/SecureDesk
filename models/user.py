import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class User(Base):
    """SQLAlchemy ORM model for users table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_type: Mapped[str] = mapped_column(String(50), default="employee", nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_group: Mapped[str] = mapped_column(String(100), nullable=False)
    groups: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    support_departments: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)

    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} user_type={self.user_type}>"
