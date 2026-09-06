import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DATABASE_NAME", "devops_monitor_pro_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
