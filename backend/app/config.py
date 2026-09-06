from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Monitor Pro"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "devops_monitor_pro"

    SECRET_KEY: str = "change-me-in-production"
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

    # Email Notification Settings
    SMTP_ENABLED: bool = False
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "DevOps Monitor Pro"

    # WhatsApp Notification Settings
    WHATSAPP_ENABLED: bool = False
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v17.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_TIMEOUT: int = 30

    # Telegram Notification Settings
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_TIMEOUT: int = 30
    TELEGRAM_PARSE_MODE: str = "HTML"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
