import uuid

import pytest


def _unique_user():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"user_{uid}@test.com",
        "username": f"user{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


@pytest.mark.asyncio
async def test_register_and_login(client):
    user = _unique_user()
    reg = await client.post("/api/auth/register", json=user)
    assert reg.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


@pytest.mark.asyncio
async def test_invalid_login(client):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "wrong"},
    )
    assert response.status_code == 401
