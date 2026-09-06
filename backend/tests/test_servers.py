import uuid

import pytest


async def _auth_headers(client):
    uid = uuid.uuid4().hex[:8]
    user = {
        "email": f"srv_{uid}@test.com",
        "username": f"srv{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_server_crud(client):
    headers = await _auth_headers(client)
    create = await client.post(
        "/api/servers/",
        headers=headers,
        json={
            "name": "Test Server",
            "ip_address": "192.168.1.10",
            "server_type": "web",
            "tags": ["test"],
        },
    )
    assert create.status_code == 200
    server = create.json()
    server_id = server["id"]
    assert server["agent_token"]

    listing = await client.get("/api/servers/", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    detail = await client.get(f"/api/servers/{server_id}", headers=headers)
    assert detail.status_code == 200

    delete = await client.delete(f"/api/servers/{server_id}", headers=headers)
    assert delete.status_code == 200
