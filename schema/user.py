import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base fields shared across User schemas."""
    name: str
    email: EmailStr
    is_active: bool = True
    user_type: str = "engineer"
    department: str
    permission_group: str


class UserCreate(UserBase):
    """Schema for User signup/registration."""
    password: str = Field(..., min_length=6, description="Plaintext password for registration")


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
