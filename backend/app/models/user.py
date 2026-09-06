import enum
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import EmailStr, Field


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Document):
    email: EmailStr = Indexed(str, unique=True)
    username: str = Indexed(str, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_verified: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        use_state_management = True
