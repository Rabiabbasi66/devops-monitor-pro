from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

from ..config import settings
from ..models.user import UserRole
from ..utils.security import validate_password_strength


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    full_name: Optional[str] = None
    password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        valid, message = validate_password_strength(value)
        if not valid:
            raise ValueError(message)
        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password and value != password:
            raise ValueError("Passwords do not match")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
