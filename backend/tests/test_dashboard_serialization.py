"""Tests for dashboard API response shape and correct field names."""
import uuid
import pytest


async def _setup_with_server(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"ds_{uid}@test.com",
        "username": f"ds{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    server = await client.post(
        "/api/servers/",
        headers=headers,
        json={"name": "Dash Server", "ip_address": "10.30.0.1", "server_type": "api", "tags": []},
    )
    return headers, server.json()


@pytest.mark.asyncio
async def test_dashboard_summary_empty(client):
    """Dashboard summary for user with no servers should return zeros."""
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"ds_empty_{uid}@test.com",
        "username": f"dsempty{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # All required top-level keys must be present
    required_keys = [
        "total_servers", "online_servers", "offline_servers",
        "warning_servers", "critical_servers",
        "pending_alerts", "critical_alerts",
        "average_cpu", "average_memory", "average_disk",
        "uptime_percentage",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"

    # Alias keys also present (for backward compat)
    for alias in ["avg_cpu", "avg_memory", "avg_disk"]:
        assert alias in data, f"Missing alias key: {alias}"

    assert data["total_servers"] == 0
    assert data["pending_alerts"] == 0


@pytest.mark.asyncio
async def test_dashboard_summary_with_server(client):
    """Dashboard summary with a server should have total_servers >= 1."""
    headers, server = await _setup_with_server(client)

    resp = await client.get("/api/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_servers"] >= 1


@pytest.mark.asyncio
async def test_dashboard_summary_after_metric_ingest(client):
    """After ingest, average_cpu / avg_cpu must reflect actual metric values."""
    headers, server = await _setup_with_server(client)

    # Ingest a known CPU value
    await client.post(
        "/api/monitoring/metrics",
        json={
            "server_id": server["id"],
            "cpu_usage": 55.0,
            "memory_usage": 70.0,
            "disk_usage": 40.0,
        },
        headers={"X-Agent-Token": server["agent_token"]},
    )

    resp = await client.get("/api/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # CPU should be around 55 (only one server)
    assert data["average_cpu"] == pytest.approx(55.0, abs=1.0)
    assert data["avg_cpu"] == pytest.approx(55.0, abs=1.0)
    assert data["average_memory"] == pytest.approx(70.0, abs=1.0)
    assert data["online_servers"] >= 1


@pytest.mark.asyncio
async def test_server_response_shape(client):
    """GET /api/servers/{id} must include all expected fields."""
    headers, server = await _setup_with_server(client)

    resp = await client.get(f"/api/servers/{server['id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    required = [
        "id", "name", "ip_address", "server_type",
        "status", "health_status",
        "cpu_usage", "memory_usage", "disk_usage", "uptime",
        "last_checked", "last_seen",
        "agent_version", "agent_status",
        "tags", "monitoring_enabled",
        "user_id", "thresholds",
        "created_at", "updated_at",
    ]
    for key in required:
        assert key in data, f"Missing field in ServerResponse: {key}"

    # agent_token must NOT be exposed on GET
    assert data.get("agent_token") is None


@pytest.mark.asyncio
async def test_server_create_returns_agent_token(client):
    """POST /api/servers/ must return agent_token so admin can configure the agent."""
    headers, server = await _setup_with_server(client)
    # The create response (stored in `server`) should have agent_token
    assert server.get("agent_token") is not None
    assert len(server["agent_token"]) > 10
