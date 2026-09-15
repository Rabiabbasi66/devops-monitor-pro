import secrets
from datetime import datetime, timedelta
from typing import Optional

from beanie import Document, Indexed
from beanie.odm.fields import ExpressionField
from pydantic import Field


def generate_verification_code() -> str:
    """Generate a secure 6-digit verification code."""
    return "".join([str(secrets.randbelow(10)) for _ in range(6)])


def hash_verification_code(code: str) -> str:
    """Generate a SHA-256 hash of the verification code."""
    import hashlib
    return hashlib.sha256(code.encode()).hexdigest()


class EmailVerification(Document):
    """Email verification code record.

    Multi-tenancy: each record belongs to a user (user_id).
    Codes are short-lived (10 minutes), single-use, and stored as hashes.
    """

    user_id: Indexed(str)
    email: Indexed(str)
    code_hash: str  # SHA-256 hash of the verification code
    expires_at: datetime
    used: bool = False
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "email_verifications"
        use_state_management = True
        indexes = [
            [("user_id", 1), ("email", 1)],
            [("expires_at", 1)],
            [("used", 1)],
        ]

    @classmethod
    def build_expiry(cls, minutes: int = 10) -> datetime:
        """Build an expiry timestamp."""
        return datetime.utcnow() + timedelta(minutes=minutes)

    def is_expired(self) -> bool:
        """Check if the verification code has expired."""
        return datetime.utcnow() > self.expires_at


def _register_expression_fields(document_class: type) -> None:
    """Pre-register Beanie ``ExpressionField`` attributes on a document class.

    Beanie normally attaches ``ExpressionField`` class attributes inside
    ``init_beanie()`` (see beanie.odm.utils.init.DocInitializer, which runs
    ``setattr(cls, k, ExpressionField(v.alias or k))`` for every model field).
    That step requires a connected MongoDB instance. Without it, Pydantic v2's
    metaclass does not expose model fields as class attributes, so building a
    query such as ``EmailVerification.user_id == user_id`` raises
    ``AttributeError: user_id``.

    Mirroring Beanie's own initialization here keeps class-level query
    construction working offline (unit tests, validation). When ``init_beanie()``
    later runs at application startup it repeats the identical ``setattr``
    calls, so behavior and collection settings are unchanged.
    """
    for field_name, field_info in document_class.model_fields.items():
        setattr(document_class, field_name, ExpressionField(field_info.alias or field_name))


_register_expression_fields(EmailVerification)
