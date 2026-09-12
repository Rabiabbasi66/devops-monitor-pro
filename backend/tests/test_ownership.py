"""Tests for server ownership enforcement — users cannot access each other's servers."""
import uuid
import pytest


def _user_data(prefix="own"):
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"{prefix}_{uid}@test.com",
        "username": f"{prefix}{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


async def _login(client, user_data):
    await client.post("/api/auth/register", json=user_data)
    login = await client.post(
        "/api/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _create_server(client, headers, name="My Server", ip="10.1.1.1"):
    resp = await client.post(
        "/api/servers/",
        headers=headers,
        json={"name": name, "ip_address": ip, "server_type": "web", "tags": []},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_user_cannot_get_another_users_server(client):
    """GET /api/servers/{id} must return 404 for another user's server."""
    headers_a = await _login(client, _user_data("a"))
    headers_b = await _login(client, _user_data("b"))

    server = await _create_server(client, headers_a, ip="10.2.1.1")

    resp = await client.get(f"/api/servers/{server['id']}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_server(client):
    """PUT /api/servers/{id} must return 404 for another user's server."""
    headers_a = await _login(client, _user_data("ua"))
    headers_b = await _login(client, _user_data("ub"))

    server = await _create_server(client, headers_a, ip="10.3.1.1")

    resp = await client.put(
        f"/api/servers/{server['id']}",
        headers=headers_b,
        json={"name": "Hijacked"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_server(client):
    """DELETE /api/servers/{id} must return 404 for another user's server."""
    headers_a = await _login(client, _user_data("da"))
    headers_b = await _login(client, _user_data("db"))

    server = await _create_server(client, headers_a, ip="10.4.1.1")

    resp = await client.delete(f"/api/servers/{server['id']}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_server_list_only_shows_own_servers(client):
    """GET /api/servers/ must only return servers belonging to the requesting user."""
    headers_a = await _login(client, _user_data("la"))
    headers_b = await _login(client, _user_data("lb"))

    server_a = await _create_server(client, headers_a, name="Server A", ip="10.5.1.1")
    await _create_server(client, headers_b, name="Server B", ip="10.5.1.2")

    list_resp = await client.get("/api/servers/", headers=headers_a)
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()]
    assert server_a["id"] in ids
    # Server B's id should NOT be in user A's list
    for srv in list_resp.json():
        assert srv["name"] != "Server B"


@pytest.mark.asyncio
async def test_agent_token_cannot_ingest_for_wrong_server(client):
    """Agent token from server A must not be used to ingest metrics for server B."""
    headers_a = await _login(client, _user_data("ata"))
    headers_b = await _login(client, _user_data("atb"))

    server_a = await _create_server(client, headers_a, name="A-Srv", ip="10.6.1.1")
    server_b = await _create_server(client, headers_b, name="B-Srv", ip="10.6.1.2")

    payload = {
        "server_id": server_b["id"],  # B's server id
        "cpu_usage": 50.0,
        "memory_usage": 50.0,
        "disk_usage": 50.0,
    }
    # Use A's agent token but claim metrics are for B
    resp = await client.post(
        "/api/monitoring/metrics",
        json=payload,
        headers={"X-Agent-Token": server_a["agent_token"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_server_list_rejected(client):
    """Requests without a JWT must be rejected with 403."""
    resp = await client.get("/api/servers/")
    assert resp.status_code == 403
