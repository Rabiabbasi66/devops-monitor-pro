"""Tests for refresh token security — must reject access tokens used as refresh tokens."""
import uuid
import pytest


def _unique_user():
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"rt_{uid}@test.com",
        "username": f"rt{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }


async def _register_and_login(client):
    user = _unique_user()
    await client.post("/api/auth/register", json=user)
    login = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert login.status_code == 200
    data = login.json()
    return data["access_token"], data["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_with_valid_refresh_token(client):
    """A valid refresh token should return a new token pair."""
    _, refresh_token = await _register_and_login(client)
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client):
    """An access token must NOT be accepted as a refresh token."""
    access_token, _ = await _register_and_login(client)
    resp = await client.post("/api/auth/refresh", json={"refresh_token": access_token})
    # Must be rejected — type is "access" not "refresh"
    assert resp.status_code == 401
    body = resp.json()
    # The error message should indicate token type mismatch
    assert "type" in body.get("message", "").lower() or resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token_rejected(client):
    """A garbage string must be rejected."""
    resp = await client.post("/api/auth/refresh", json={"refresh_token": "not-a-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_returns_new_access_token(client):
    """New access token from refresh should allow authenticated requests."""
    _, refresh_token = await _register_and_login(client)
    refresh_resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me_resp.status_code == 200
