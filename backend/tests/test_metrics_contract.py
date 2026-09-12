"""Tests for agent → API → DB metric contract consistency."""
import uuid
import pytest


async def _setup(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"mc_{uid}@test.com",
        "username": f"mc{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    create = await client.post(
        "/api/servers/",
        headers=headers,
        json={
            "name": "Contract Server",
            "ip_address": "10.20.0.1",
            "server_type": "web",
            "tags": [],
        },
    )
    return headers, create.json()


@pytest.mark.asyncio
async def test_server_fields_updated_after_metrics_ingest(client):
    """Ingested metrics must update the corresponding Server document fields."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    payload = {
        "server_id": sid,
        "cpu_usage": 42.5,
        "memory_usage": 67.3,
        "disk_usage": 55.1,
        "uptime": 12345.0,
        "hostname": "test-host-001",
        "operating_system": "Ubuntu 22.04",
        "os_version": "22.04",
        "architecture": "x86_64",
        "agent_version": "2.0.0",
        "network_sent": 1000000.0,
        "network_received": 2000000.0,
    }

    resp = await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": tok},
    )
    assert resp.status_code == 200

    # Verify server document reflects the ingested values
    srv = await client.get(f"/api/servers/{sid}", headers=headers)
    assert srv.status_code == 200
    data = srv.json()
    assert data["cpu_usage"] == pytest.approx(42.5, abs=0.1)
    assert data["memory_usage"] == pytest.approx(67.3, abs=0.1)
    assert data["disk_usage"] == pytest.approx(55.1, abs=0.1)
    assert data["uptime"] == pytest.approx(12345.0, abs=1.0)
    assert data["hostname"] == "test-host-001"
    assert data["operating_system"] == "Ubuntu 22.04"
    assert data["os_version"] == "22.04"
    assert data["architecture"] == "x86_64"
    assert data["agent_version"] == "2.0.0"
    assert data["agent_status"] == "active"
    assert data["status"] == "running"
    assert data["last_seen"] is not None


@pytest.mark.asyncio
async def test_metrics_stored_in_history(client):
    """Ingested metrics must appear in the server metrics history endpoint."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    for i in range(3):
        await client.post(
            "/api/monitoring/metrics",
            json={
                "server_id": sid,
                "cpu_usage": float(10 + i * 10),
                "memory_usage": 50.0,
                "disk_usage": 30.0,
            },
            headers={"X-Agent-Token": tok},
        )

    metrics = await client.get(
        f"/api/servers/{sid}/metrics", headers=headers, params={"hours": 1, "limit": 10}
    )
    assert metrics.status_code == 200
    data = metrics.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_latest_metric_endpoint(client):
    """GET /servers/{id}/metrics/latest returns the most recent metric."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    await client.post(
        "/api/monitoring/metrics",
        json={"server_id": sid, "cpu_usage": 77.0, "memory_usage": 50.0, "disk_usage": 30.0},
        headers={"X-Agent-Token": tok},
    )

    latest = await client.get(f"/api/servers/{sid}/metrics/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json()["cpu_usage"] == pytest.approx(77.0, abs=0.1)


@pytest.mark.asyncio
async def test_metric_ingest_ignores_unknown_fields(client):
    """Agent may send extra fields (like process_count from old agents); they must not cause errors."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    payload = {
        "server_id": sid,
        "cpu_usage": 20.0,
        "memory_usage": 30.0,
        "disk_usage": 10.0,
        # Legacy field from old agents — must be ignored, not cause 422
        "process_count": 120,
        # Another unknown field
        "some_future_field": "value",
    }
    resp = await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": tok},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_agent_token_rejected(client):
    """Metrics sent with a wrong agent token must be rejected with 401."""
    headers, server = await _setup(client)
    sid = server["id"]

    resp = await client.post(
        "/api/monitoring/metrics",
        json={"server_id": sid, "cpu_usage": 10.0, "memory_usage": 10.0, "disk_usage": 10.0},
        headers={"X-Agent-Token": "invalid-token-xyz"},
    )
    assert resp.status_code == 401
