import uuid

import pytest


@pytest.mark.asyncio
async def test_dashboard_summary(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"dash_{uid}@test.com",
        "username": f"dash{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_servers" in data
    assert "pending_alerts" in data
