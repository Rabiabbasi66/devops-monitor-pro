import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    # Production API by default; local development overrides this via
    # agent/.env (see .env.example) — no localhost URL ships in the packaged agent.
    API_URL: str = "https://devops-monitor-pro.vercel.app/api"
    SERVER_ID: str = ""
    AGENT_TOKEN: str = ""
    INTERVAL_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = AgentSettings()

if not settings.SERVER_ID:
    settings.SERVER_ID = os.getenv("SERVER_ID", "")
if not settings.AGENT_TOKEN:
    settings.AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")
