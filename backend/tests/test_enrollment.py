"""Tests for agent enrollment flow — token generation, use, expiry, single-use."""
import uuid
import pytest


def _unique_user():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"enr_{uid}@test.com",
        "username": f"enr{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


async def _setup(client):
    """Register, login, create server; return headers + server dict."""
    user = _unique_user()
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
            "name": "Enroll Server",
            "ip_address": "192.168.100.1",
            "server_type": "api",
            "tags": [],
        },
    )
    assert create.status_code == 200
    return headers, create.json()


@pytest.mark.asyncio
async def test_generate_enrollment_token(client):
    """Should produce a valid enrollment token for a valid server."""
    headers, server = await _setup(client)
    resp = await client.post(
        f"/api/agents/{server['id']}/enrollment", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "enrollment_token" in data
    assert data["server_id"] == server["id"]
    assert "api_url" in data
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_enroll_agent_with_valid_token(client):
    """Should exchange a valid enrollment token for a permanent agent token."""
    headers, server = await _setup(client)

    # Generate enrollment token
    token_resp = await client.post(
        f"/api/agents/{server['id']}/enrollment", headers=headers
    )
    enrollment_token = token_resp.json()["enrollment_token"]

    # Enroll the agent
    enroll_resp = await client.post(
        "/api/agents/enroll",
        json={"enrollment_token": enrollment_token},
    )
    assert enroll_resp.status_code == 200
    data = enroll_resp.json()
    assert "agent_token" in data
    assert "server_id" in data
    assert data["server_id"] == server["id"]


@pytest.mark.asyncio
async def test_enrollment_token_is_single_use(client):
    """Using an enrollment token a second time must fail."""
    headers, server = await _setup(client)

    token_resp = await client.post(
        f"/api/agents/{server['id']}/enrollment", headers=headers
    )
    enrollment_token = token_resp.json()["enrollment_token"]

    # First use — succeeds
    r1 = await client.post(
        "/api/agents/enroll", json={"enrollment_token": enrollment_token}
    )
    assert r1.status_code == 200

    # Second use — must be rejected
    r2 = await client.post(
        "/api/agents/enroll", json={"enrollment_token": enrollment_token}
    )
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_enroll_with_invalid_token_rejected(client):
    """A bogus enrollment token must be rejected."""
    resp = await client.post(
        "/api/agents/enroll", json={"enrollment_token": "bogus-token-xyz"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_enrollment_token_requires_server_ownership(client):
    """Generating an enrollment token for another user's server must fail."""
    # User A creates a server
    headers_a, server = await _setup(client)

    # User B tries to generate enrollment token for User A's server
    uid = uuid.uuid4().hex[:8]
    user_b = {
        "email": f"enrb_{uid}@test.com",
        "username": f"enrb{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user_b)
    login_b = await client.post(
        "/api/auth/login",
        json={"email": user_b["email"], "password": user_b["password"]},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.post(
        f"/api/agents/{server['id']}/enrollment", headers=headers_b
    )
    assert resp.status_code == 404  # Server not found for this user


@pytest.mark.asyncio
async def test_enrolled_agent_token_works_for_metrics(client):
    """Permanent agent token from enrollment should accept metric ingestion."""
    headers, server = await _setup(client)

    # Enroll
    token_resp = await client.post(
        f"/api/agents/{server['id']}/enrollment", headers=headers
    )
    enrollment_token = token_resp.json()["enrollment_token"]
    enroll_resp = await client.post(
        "/api/agents/enroll", json={"enrollment_token": enrollment_token}
    )
    agent_token = enroll_resp.json()["agent_token"]

    # Send metrics using the enrolled token
    payload = {
        "server_id": server["id"],
        "cpu_usage": 30.0,
        "memory_usage": 40.0,
        "disk_usage": 25.0,
        "uptime": 1000.0,
        "hostname": "enrolled-host",
        "operating_system": "Linux 6.1",
        "agent_version": "2.0.0",
    }
    metric_resp = await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": agent_token},
    )
    assert metric_resp.status_code == 200
    assert metric_resp.json()["success"] is True

    # Verify server was updated
    server_resp = await client.get(
        f"/api/servers/{server['id']}", headers=headers
    )
    updated = server_resp.json()
    assert updated["hostname"] == "enrolled-host"
    assert updated["cpu_usage"] == 30.0
    assert updated["status"] == "running"
    assert updated["agent_version"] == "2.0.0"
    assert updated["agent_status"] == "active"
