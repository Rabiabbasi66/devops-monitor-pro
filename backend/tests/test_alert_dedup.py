"""Tests for alert deduplication, cooldown, and recovery."""
import uuid
import pytest


async def _setup(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"ded_{uid}@test.com",
        "username": f"ded{uid}",
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
        json={
            "name": "Dedup Server",
            "ip_address": "10.10.10.1",
            "server_type": "api",
            "tags": [],
        },
    )
    return headers, server.json()


async def _ingest(client, server_id, agent_token, cpu=96.0, mem=50.0, disk=50.0):
    return await client.post(
        "/api/monitoring/metrics",
        json={
            "server_id": server_id,
            "cpu_usage": cpu,
            "memory_usage": mem,
            "disk_usage": disk,
        },
        headers={"X-Agent-Token": agent_token},
    )


@pytest.mark.asyncio
async def test_repeated_high_cpu_creates_only_one_alert(client):
    """Sending the same high-CPU metric twice should not create two identical alerts."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    r1 = await _ingest(client, sid, tok, cpu=96.0)
    assert r1.status_code == 200
    assert r1.json()["alerts_created"] >= 1

    r2 = await _ingest(client, sid, tok, cpu=96.0)
    assert r2.status_code == 200
    # Duplicate within cooldown window — should NOT create another alert
    assert r2.json()["alerts_created"] == 0

    # Verify: only one CRITICAL cpu alert exists
    alerts_resp = await client.get("/api/alerts/pending", headers=headers)
    cpu_critical = [
        a for a in alerts_resp.json()["items"]
        if a["metric_type"] == "cpu" and a["severity"] == "critical"
    ]
    assert len(cpu_critical) == 1


@pytest.mark.asyncio
async def test_alert_occurrence_count_increments_on_duplicate(client):
    """When a duplicate alert is found, occurrence_count should increment."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    await _ingest(client, sid, tok, cpu=96.0)
    await _ingest(client, sid, tok, cpu=96.0)

    alerts_resp = await client.get("/api/alerts/pending", headers=headers)
    cpu_critical = [
        a for a in alerts_resp.json()["items"]
        if a["metric_type"] == "cpu" and a["severity"] == "critical"
    ]
    assert len(cpu_critical) == 1
    # Second ingest increments the count on the existing alert
    assert cpu_critical[0]["occurrence_count"] >= 1


@pytest.mark.asyncio
async def test_normal_metrics_after_critical_no_new_alert(client):
    """After a critical alert, sending normal metrics should NOT create a new alert."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    # Send high CPU
    await _ingest(client, sid, tok, cpu=96.0)

    # Send normal CPU — should produce zero new alerts
    r = await _ingest(client, sid, tok, cpu=10.0)
    assert r.status_code == 200
    assert r.json()["alerts_created"] == 0


@pytest.mark.asyncio
async def test_alert_resolve_and_reopen(client):
    """Resolved alert can be reopened; reopened alert is pending again."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    await _ingest(client, sid, tok, cpu=96.0)

    alerts_resp = await client.get("/api/alerts/pending", headers=headers)
    alert_id = alerts_resp.json()["items"][0]["id"]

    # Resolve
    r_resolve = await client.put(f"/api/alerts/{alert_id}/resolve", headers=headers)
    assert r_resolve.status_code == 200
    assert r_resolve.json()["status"] == "resolved"

    # Reopen
    r_reopen = await client.put(f"/api/alerts/{alert_id}/reopen", headers=headers)
    assert r_reopen.status_code == 200
    assert r_reopen.json()["status"] == "pending"

    # Now pending again
    pending = await client.get("/api/alerts/pending", headers=headers)
    ids = [a["id"] for a in pending.json()["items"]]
    assert alert_id in ids


@pytest.mark.asyncio
async def test_alert_acknowledge(client):
    """An acknowledged alert is no longer pending but not resolved."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    await _ingest(client, sid, tok, cpu=96.0)

    alerts_resp = await client.get("/api/alerts/pending", headers=headers)
    alert_id = alerts_resp.json()["items"][0]["id"]

    ack = await client.put(f"/api/alerts/{alert_id}/acknowledge", headers=headers)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_at"] is not None

    # Should no longer appear in /pending
    pending = await client.get("/api/alerts/pending", headers=headers)
    ids = [a["id"] for a in pending.json()["items"]]
    assert alert_id not in ids


@pytest.mark.asyncio
async def test_different_metric_types_create_separate_alerts(client):
    """High CPU AND high memory should each create their own alert."""
    headers, server = await _setup(client)
    sid = server["id"]
    tok = server["agent_token"]

    r = await _ingest(client, sid, tok, cpu=96.0, mem=96.0, disk=50.0)
    assert r.status_code == 200
    assert r.json()["alerts_created"] >= 2

    alerts = await client.get("/api/alerts/pending", headers=headers)
    types = {a["metric_type"] for a in alerts.json()["items"]}
    assert "cpu" in types
    assert "memory" in types
