import re
from typing import Optional

from beanie import PydanticObjectId

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# E.164: country code (1-9) followed by up to 14 more digits
E164_REGEX = re.compile(r"^[1-9]\d{7,14}$")


def is_valid_object_id(value: str) -> bool:
    try:
        PydanticObjectId(value)
        return True
    except Exception:
        return False


def validate_email_format(email: str) -> bool:
    """Return True when the string is a syntactically valid email address."""
    if not email or len(email) > 254:
        return False
    if not EMAIL_REGEX.match(email.strip()):
        return False
    try:
        # email-validator is already a project dependency
        from email_validator import validate_email as _validate

        _validate(email.strip(), check_deliverability=False)
        return True
    except ImportError:
        return True  # fall back to the regex check above
    except Exception:
        return False


def normalize_phone_e164(phone: str) -> Optional[str]:
    """Normalize a phone number to E.164 (+<countrycode><number>).

    Accepts inputs like "+92 300 1234567", "923001234567", "+92-300-1234567".
    Returns None when the value cannot be represented in E.164.
    """
    if not phone:
        return None
    cleaned = re.sub(r"[\s\-().]", "", str(phone).strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned.isdigit():
        return None
    if not E164_REGEX.match(cleaned):
        return None
    return f"+{cleaned}"


def validate_phone_e164(phone: str) -> bool:
    """Return True when the phone number is E.164 compatible."""
    return normalize_phone_e164(phone) is not None
