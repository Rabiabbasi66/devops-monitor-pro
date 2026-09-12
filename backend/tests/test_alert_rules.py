"""Tests for alert rule CRUD and ownership."""
import uuid
import pytest


def _unique_user(prefix="ar"):
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"{prefix}_{uid}@test.com",
        "username": f"{prefix}{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


async def _setup(client):
    user = _unique_user()
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers


@pytest.mark.asyncio
async def test_create_alert_rule(client):
    headers = await _setup(client)
    resp = await client.post(
        "/api/alert-rules/",
        headers=headers,
        json={
            "name": "High CPU Rule",
            "metric_type": "cpu",
            "operator": ">",
            "warning_threshold": 80.0,
            "critical_threshold": 95.0,
            "cooldown_seconds": 300,
            "enabled": True,
            "severity": "high",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "High CPU Rule"
    assert data["metric_type"] == "cpu"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_alert_rules(client):
    headers = await _setup(client)
    await client.post(
        "/api/alert-rules/",
        headers=headers,
        json={
            "name": "List Rule",
            "metric_type": "memory",
            "warning_threshold": 85.0,
            "critical_threshold": 95.0,
        },
    )
    resp = await client.get("/api/alert-rules/", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_alert_rule(client):
    headers = await _setup(client)
    create = await client.post(
        "/api/alert-rules/",
        headers=headers,
        json={
            "name": "Get Rule",
            "metric_type": "disk",
            "warning_threshold": 80.0,
            "critical_threshold": 90.0,
        },
    )
    rule_id = create.json()["id"]

    resp = await client.get(f"/api/alert-rules/{rule_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == rule_id


@pytest.mark.asyncio
async def test_enable_disable_alert_rule(client):
    headers = await _setup(client)
    create = await client.post(
        "/api/alert-rules/",
        headers=headers,
        json={
            "name": "Toggle Rule",
            "metric_type": "cpu",
            "warning_threshold": 80.0,
            "critical_threshold": 95.0,
            "enabled": True,
        },
    )
    rule_id = create.json()["id"]

    # Disable
    r_disable = await client.post(f"/api/alert-rules/{rule_id}/disable", headers=headers)
    assert r_disable.status_code == 200
    assert r_disable.json()["enabled"] is False

    # Enable
    r_enable = await client.post(f"/api/alert-rules/{rule_id}/enable", headers=headers)
    assert r_enable.status_code == 200
    assert r_enable.json()["enabled"] is True


@pytest.mark.asyncio
async def test_delete_alert_rule(client):
    headers = await _setup(client)
    create = await client.post(
        "/api/alert-rules/",
        headers=headers,
        json={
            "name": "Delete Rule",
            "metric_type": "memory",
            "warning_threshold": 85.0,
            "critical_threshold": 95.0,
        },
    )
    rule_id = create.json()["id"]

    del_resp = await client.delete(f"/api/alert-rules/{rule_id}", headers=headers)
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/alert-rules/{rule_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_alert_rule_ownership(client):
    headers_a = await _setup(client)
    headers_b = await _setup(client)

    create = await client.post(
        "/api/alert-rules/",
        headers=headers_a,
        json={
            "name": "Private Rule",
            "metric_type": "disk",
            "warning_threshold": 80.0,
            "critical_threshold": 90.0,
        },
    )
    rule_id = create.json()["id"]

    resp = await client.get(f"/api/alert-rules/{rule_id}", headers=headers_b)
    assert resp.status_code == 404
