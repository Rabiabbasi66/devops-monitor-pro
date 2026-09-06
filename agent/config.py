import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    API_URL: str = "http://localhost:8000/api"
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

