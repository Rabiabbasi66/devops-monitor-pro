import uuid

import pytest


async def _setup_server(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"met_{uid}@test.com",
        "username": f"met{uid}",
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
            "name": "Metric Server",
            "ip_address": "10.0.0.1",
            "server_type": "api",
            "tags": [],
        },
    )
    server = create.json()
    return headers, server


@pytest.mark.asyncio
async def test_metric_ingest(client):
    headers, server = await _setup_server(client)
    payload = {
        "server_id": server["id"],
        "cpu_usage": 50.0,
        "memory_usage": 60.0,
        "disk_usage": 40.0,
        "network_received": 1000,
        "network_sent": 500,
        "uptime": 3600,
        "process_count": 120,
    }
    response = await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={**headers, "X-Agent-Token": server["agent_token"]},
    )
    assert response.status_code == 200

    metrics = await client.get(
        f"/api/servers/{server['id']}/metrics", headers=headers
    )
    assert metrics.status_code == 200
    assert metrics.json()["total"] >= 1
