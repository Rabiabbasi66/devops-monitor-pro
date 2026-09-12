"""Live smoke test against a running uvicorn server (requirement 19)."""
import json
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8021"

results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition), extra))
    print(f"{'PASS' if condition else 'FAIL'}: {name} {extra}")


def main():
    client = httpx.Client(timeout=20)

    r = client.get(f"{BASE}/")
    check("GET / returns 200", r.status_code == 200)
    r = client.get(f"{BASE}/docs")
    check("GET /docs returns 200", r.status_code == 200)
    r = client.get(f"{BASE}/health")
    check("GET /health returns 200", r.status_code == 200 and r.json().get("status") in ("healthy", "degraded"), str(r.json())[:80])

    # Register + login
    uid = uuid.uuid4().hex[:8]
    payload = {
        "email": f"smoke_{uid}@test.com",
        "username": f"smoke{uid}",
        "password": "Password1!",
        "confirm_password": "Password1!",
    }
    client.post(f"{BASE}/api/auth/register", json=payload)
    login = client.post(f"{BASE}/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    check("POST /api/auth/login returns 200", login.status_code == 200)
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Notification channel API
    r = client.get(f"{BASE}/api/notifications/settings/", headers=headers)
    check("GET /api/notifications/settings/ returns 200 (empty list)", r.status_code == 200 and r.json() == [])

    # Provider status endpoint (no secrets)
    r = client.get(f"{BASE}/api/notifications/settings/providers/status", headers=headers)
    body = json.dumps(r.json())
    check("GET /api/notifications/settings/providers/status returns 200", r.status_code == 200)
    providers = r.json().get("providers", {})
    check("Provider status has email/whatsapp/telegram keys", set(providers) >= {"email", "whatsapp", "telegram"}, json.dumps(providers)[:200])
    check("Provider status contains no credential VALUES", "your-super-secret" not in body and "platform-app-password" not in body)

    # Create WhatsApp channel with E.164 number
    r = client.post(f"{BASE}/api/notifications/settings/", headers=headers, json={
        "provider": "whatsapp", "enabled": True, "recipient": "+92 300 1234567",
    })
    check("POST create WhatsApp channel (E.164) returns 200", r.status_code == 200, r.text[:120])
    wa = r.json()

    # Invalid phone rejected
    r = client.post(f"{BASE}/api/notifications/settings/", headers=headers, json={
        "provider": "whatsapp", "recipient": "12ab",
    })
    check("POST invalid WhatsApp phone rejected with 400", r.status_code == 400, r.text[:100])

    # Create email channel
    r = client.post(f"{BASE}/api/notifications/settings/", headers=headers, json={
        "provider": "email", "enabled": True, "recipient": "smoke@example.com",
    })
    check("POST create Email channel returns 200", r.status_code == 200)

    # Test notification on WhatsApp (platform creds empty -> useful error, no secrets)
    r = client.post(f"{BASE}/api/notifications/settings/test", headers=headers, json={
        "provider": "whatsapp", "recipient": "+923001234567",
    })
    details = r.json().get("details", {})
    check("POST /test WhatsApp returns structured result", r.status_code == 200 and "success" in details)
    allowed_errors = {
        "whatsapp provider is not enabled",
        "whatsapp provider is not configured",
        "whatsapp provider is not configured (missing phone number id)",
        "whatsapp provider is not configured (missing access token)",
    }
    check("Test error is useful and secret-free", str(details.get("error", "")).lower() in allowed_errors, str(details.get("error")))

    # Telegram connect (platform bot not configured -> 503, or success if configured)
    r = client.post(f"{BASE}/api/notifications/settings/telegram/connect", headers=headers)
    check("POST /telegram/connect responds (200 or 503 if unconfigured)", r.status_code in (200, 503), r.text[:120])

    # Update + list + delete channel
    r = client.put(f"{BASE}/api/notifications/settings/{wa['id']}", headers=headers, json={"min_severity": "critical"})
    check("PUT update channel returns 200", r.status_code == 200 and r.json()["min_severity"] == "critical")
    r = client.get(f"{BASE}/api/notifications/settings/", headers=headers)
    check("GET list channels returns created channels", r.status_code == 200 and len(r.json()) >= 2)
    r = client.delete(f"{BASE}/api/notifications/settings/{wa['id']}", headers=headers)
    check("DELETE channel returns 200", r.status_code == 200)

    # Server + high-memory metrics ingestion (memory 99 >= critical 95)
    r = client.post(f"{BASE}/api/servers/", headers=headers, json={
        "name": "SmokeSrv", "ip_address": "10.10.10.10", "server_type": "web", "tags": [],
    })
    check("POST /api/servers/ returns 200", r.status_code == 200)
    server = r.json()
    r = client.post(f"{BASE}/api/monitoring/metrics", headers={"X-Agent-Token": server["agent_token"]}, json={
        "server_id": server["id"], "cpu_usage": 50.0, "memory_usage": 99.0, "disk_usage": 50.0,
    })
    check("POST /api/monitoring/metrics returns 200 (notification attempted)", r.status_code == 200, r.text[:100])
    r = client.get(f"{BASE}/api/alerts", headers=headers)
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    check("High-memory alert was created", any(a.get("server_id") == server["id"] for a in items))

    # Cleanup
    channels = client.get(f"{BASE}/api/notifications/settings/", headers=headers).json()
    for ch in channels:
        client.delete(f"{BASE}/api/notifications/settings/{ch['id']}", headers=headers)
    client.delete(f"{BASE}/api/servers/{server['id']}", headers=headers)

    failed = [r for r in results if not r[1]]
    print(f"\nSMOKE RESULT: {len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
