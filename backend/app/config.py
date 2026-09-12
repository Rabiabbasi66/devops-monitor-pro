from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so the SAME backend/.env is loaded no
# matter which working directory `uvicorn app.main:app` is started from.
# (A relative "env_file" would silently resolve against the CWD instead.)
# config.py lives in backend/app/, so the backend root is one level up.
BASE_DIR = Path(__file__).resolve().parent.parent  # -> backend/


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Monitor Pro"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "devops_monitor_pro"

    SECRET_KEY: str = "change-me-in-production-use-a-strong-random-string-at-least-32-characters"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: List[str] = ["*"]
    FRONTEND_URL: str = "http://localhost:8501"
    BACKEND_URL: str = "http://localhost:8000"

    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    METRIC_RETENTION_DAYS: int = 30
    ALERT_COOLDOWN_SECONDS: int = 300
    SERVER_OFFLINE_THRESHOLD_SECONDS: int = 120
    HEALTH_CHECK_INTERVAL_SECONDS: int = 60

    # Security Settings
    RATE_LIMIT_PER_MINUTE: int = 60
    PASSWORD_MIN_LENGTH: int = 8
    REQUIRE_PASSWORD_SPECIAL_CHARS: bool = True
    SESSION_TIMEOUT_MINUTES: int = 60
    ENABLE_CORS_HEADERS: bool = True

    # Email Notification Settings
    SMTP_ENABLED: bool = False
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "DevOps Monitor Pro"

    # WhatsApp Notification Settings (platform-managed provider credentials)
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v17.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_TIMEOUT: int = 30

    # Telegram Notification Settings (platform-managed bot credentials)
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_TIMEOUT: int = 30
    TELEGRAM_PARSE_MODE: str = "HTML"
    # Optional static bot username for deep links (skips getMe lookup)
    TELEGRAM_BOT_USERNAME: str = ""
    # Shared secret used to verify Telegram webhook calls (set_webhook secret_token)
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # How long a one-time Telegram connection token stays valid
    TELEGRAM_CONNECT_TOKEN_EXPIRE_MINUTES: int = 15

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Fail fast: refuse to start in production with a weak/default signing key.
WEAK_SECRET_KEY_MARKERS = ("change-me", "your-", "example", "placeholder", "secret")
if (
    settings.ENVIRONMENT == "production"
    and (
        not settings.SECRET_KEY
        or len(settings.SECRET_KEY) < 32
        or any(m in settings.SECRET_KEY.lower() for m in WEAK_SECRET_KEY_MARKERS)
    )
):
    raise RuntimeError(
        "Refusing to start: ENVIRONMENT=production requires a strong SECRET_KEY "
        "of at least 32 random characters (set it in backend/.env)."
    )

