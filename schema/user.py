import uuid
from datetime import datetime
from typing import Optional

from core.permissions import Department, Role

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base fields shared across User schemas."""
    name: str
    email: EmailStr
    is_active: bool = True
    user_type: Role = Role.EMPLOYEE
    department: Department
    permission_group: str = ""
    groups: list[str] = Field(default_factory=list)
    support_departments: list[Department] = Field(default_factory=list)


class UserCreate(UserBase):
    """Schema for User signup/registration."""
    model_config = ConfigDict(extra="forbid")
    password: str = Field(..., min_length=12, max_length=72, description="Account password")


    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    """Schema for User login."""
    email: EmailStr
    password: str


class UserRead(UserBase):
    """Schema for reading user data (excluding sensitive fields like password)."""
    id: uuid.UUID
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Response returned upon successful authentication / signup."""
    user: UserRead
    token: str
    token_type: str = "bearer"


# Backward-compatible alias for existing imports
User = UserCreate
