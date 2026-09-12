"""Tests for incident management CRUD and lifecycle."""
import uuid
import pytest


def _unique_user(prefix="inc"):
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
async def test_create_incident(client):
    """Should create an incident and return it."""
    headers = await _setup(client)
    resp = await client.post(
        "/api/incidents/",
        headers=headers,
        json={
            "title": "DB Outage",
            "description": "Primary database is down",
            "severity": "critical",
            "affected_servers": [],
            "related_alerts": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "DB Outage"
    assert data["status"] == "open"
    assert data["severity"] == "critical"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_incidents(client):
    """Should return the user's incidents."""
    headers = await _setup(client)
    await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Incident List Test", "severity": "high"},
    )
    resp = await client.get("/api/incidents/", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_incident(client):
    """Should retrieve a single incident by ID."""
    headers = await _setup(client)
    create = await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Get Test", "severity": "warning"},
    )
    incident_id = create.json()["id"]

    resp = await client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == incident_id


@pytest.mark.asyncio
async def test_acknowledge_incident(client):
    """Acknowledging an incident should set status to investigating."""
    headers = await _setup(client)
    create = await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Ack Test", "severity": "high"},
    )
    incident_id = create.json()["id"]

    resp = await client.post(f"/api/incidents/{incident_id}/acknowledge", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "investigating"
    assert resp.json()["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_resolve_incident(client):
    """Resolving an incident should set status to resolved and record timestamp."""
    headers = await _setup(client)
    create = await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Resolve Test", "severity": "critical"},
    )
    incident_id = create.json()["id"]

    resp = await client.post(f"/api/incidents/{incident_id}/resolve", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_reopen_incident(client):
    """Reopening a resolved incident should return it to open status."""
    headers = await _setup(client)
    create = await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Reopen Test", "severity": "high"},
    )
    incident_id = create.json()["id"]

    await client.post(f"/api/incidents/{incident_id}/resolve", headers=headers)

    resp = await client.post(f"/api/incidents/{incident_id}/reopen", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"


@pytest.mark.asyncio
async def test_delete_incident(client):
    """Deleted incident should return 404 on subsequent GET."""
    headers = await _setup(client)
    create = await client.post(
        "/api/incidents/",
        headers=headers,
        json={"title": "Delete Test", "severity": "info"},
    )
    incident_id = create.json()["id"]

    del_resp = await client.delete(f"/api/incidents/{incident_id}", headers=headers)
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_incident_ownership(client):
    """User B should not be able to access User A's incident."""
    headers_a = await _setup(client)
    headers_b = await _setup(client)

    create = await client.post(
        "/api/incidents/",
        headers=headers_a,
        json={"title": "Private Incident", "severity": "high"},
    )
    incident_id = create.json()["id"]

    resp = await client.get(f"/api/incidents/{incident_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_incidents_by_status(client):
    """Incidents can be filtered by status."""
    headers = await _setup(client)

    # Create two incidents
    inc1 = await client.post(
        "/api/incidents/", headers=headers,
        json={"title": "Open One", "severity": "high"},
    )
    inc2 = await client.post(
        "/api/incidents/", headers=headers,
        json={"title": "Open Two", "severity": "critical"},
    )

    # Resolve one
    await client.post(f"/api/incidents/{inc1.json()['id']}/resolve", headers=headers)

    # Filter by resolved
    resp = await client.get(
        "/api/incidents/", headers=headers, params={"status": "resolved"}
    )
    assert resp.status_code == 200
    statuses = {i["status"] for i in resp.json()}
    assert "resolved" in statuses
    assert "open" not in statuses
