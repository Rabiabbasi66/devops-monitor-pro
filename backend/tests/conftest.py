import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "devops_monitor_pro_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

# Deterministic notification provider defaults for tests.
# Real environment variables take precedence over backend/.env in
# pydantic-settings, so this guarantees tests start from a known state
# regardless of the developer's local .env. Individual tests override
# settings explicitly via patch.object where needed.
os.environ.setdefault("SMTP_ENABLED", "false")
os.environ.setdefault("WHATSAPP_ENABLED", "false")
os.environ.setdefault("TELEGRAM_ENABLED", "false")

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # Use lifespan context so Beanie (and other startup tasks) are initialised
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
