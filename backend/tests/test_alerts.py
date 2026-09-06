import uuid

import pytest


async def _setup(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"al_{uid}@test.com",
        "username": f"al{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    create = await client.post(
        "/api/servers/",
        headers=headers,
        json={
            "name": "Alert Server",
            "ip_address": "10.0.0.2",
            "server_type": "web",
            "tags": [],
        },
    )
    return headers, create.json()


@pytest.mark.asyncio
async def test_alert_on_high_cpu(client):
    headers, server = await _setup(client)
    payload = {
        "server_id": server["id"],
        "cpu_usage": 96.0,
        "memory_usage": 50.0,
        "disk_usage": 40.0,
    }
    await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": server["agent_token"]},
    )
    await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": server["agent_token"]},
    )
    alerts = await client.get("/api/alerts/pending", headers=headers)
    assert alerts.status_code == 200
    items = alerts.json()["items"]
    assert len(items) >= 1

    alert_id = items[0]["id"]
    resolve = await client.put(f"/api/alerts/{alert_id}/resolve", headers=headers)
    assert resolve.status_code == 200
