from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.permissions import require_account_admin
from core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from models.user import User
from schema.user import UserCreate, UserLogin, UserRead, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    administrator: User = Depends(require_account_admin),
):
    """
    Administrator-only account creation:
    - Validates email uniqueness
    - Securely hashes password
    - Stores user record in PostgreSQL
    - Returns the created user profile
    """
    # Check if email is already registered
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    # Create new user instance with hashed password
    new_user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=payload.is_active,
        user_type=payload.user_type,
        department=payload.department,
        permission_group=payload.permission_group,
        groups=payload.groups,
        support_departments=[department.value for department in payload.support_departments],
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserRead.model_validate(new_user)


@router.post("/login", response_model=UserResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticates an existing user:
    - Validates credentials
    - Verifies account active status
    - Updates last_login timestamp
    - Returns user details and a JWT access token
    """
    # Lookup user by email
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    # Generate JWT token
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "user_type": user.user_type,
        }
    )

    return UserResponse(
        user=UserRead.model_validate(user),
        token=token,
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.
    Requires Bearer token in Authorization header.
    """
    return UserRead.model_validate(current_user)
