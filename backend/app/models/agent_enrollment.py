import secrets
from datetime import datetime, timedelta
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class AgentEnrollment(Document):
    server_id: Indexed(str)
    user_id: Indexed(str)
    token_hash: str
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    used_at: Optional[datetime] = None

    class Settings:
        name = "agent_enrollments"
        use_state_management = True
        indexes = [
            [("server_id", 1)],
            [("user_id", 1)],
            [("token_hash", 1), ("used", 1)],
            [("expires_at", 1)],
        ]


class EnrollmentRequest(BaseModel):
    enrollment_token: str


class EnrollmentResponse(BaseModel):
    server_id: str
    agent_token: str
    api_url: str
    interval_seconds: int


class EnrollmentCreateResponse(BaseModel):
    enrollment_token: str
    server_id: str
    api_url: str
    expires_at: datetime


def generate_enrollment_token() -> str:
    """Generate a cryptographically secure enrollment token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()
