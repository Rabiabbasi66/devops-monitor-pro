# DevOps Monitor Pro

Production-ready infrastructure monitoring platform: **FastAPI + MongoDB (Beanie)** backend, **Streamlit** dashboard, and a **psutil-based monitoring agent** with automatic enrollment, threshold alerting, incident management and multi-channel notifications (Email/SMTP, WhatsApp, Telegram).

All features documented below are implemented and verified by the test suite (`backend/tests/`, 113 tests) plus live end-to-end checks.

## Features

- **Users & Auth** — JWT access + refresh tokens, bcrypt password hashing, admin/user roles, ownership enforced on every protected route
- **Server Management** — CRUD, per-server alert thresholds, environment/tags/description metadata, monitoring enable/disable, cascade delete of related data
- **Agent Enrollment** — short-lived (20 min), single-use enrollment tokens exchanged for permanent agent tokens; tokens stored SHA-256 hashed
- **Metric Ingestion** — agent POSTs CPU/memory/disk/network/uptime/system info with `X-Agent-Token`; unknown fields ignored for backward compatibility
- **Health Calculation** — healthy / warning / critical / offline / unknown based on thresholds and last-seen age
- **Alert Engine** — threshold evaluation on every ingest, deduplication within a cooldown window (occurrence counting instead of duplicate alerts), acknowledge/resolve/reopen, offline ("connectivity") alerts
- **Recovery & Offline Detection** — background loop flags servers with no metrics past `SERVER_OFFLINE_THRESHOLD_SECONDS`, raises a critical connectivity alert and sends notifications; next successful ingest emits a recovery notification
- **Alert Rules** — user-scoped CRUD with per-rule metric, operator, warning/critical thresholds, severity, cooldown and enable/disable
- **Incidents** — grouped response records with acknowledge/resolve/reopen lifecycle, related-alert linking, ownership enforced
- **Notifications** — in-app center plus external channels per user: Email (SMTP), WhatsApp (Meta Cloud API), Telegram (Bot API)
  - Per-channel **minimum severity** filter (info/warning/high/critical)
  - Per-channel **notification types** (alert / recovery / offline / security)
  - Per-channel **cooldown** (seconds between sends)
  - **Test notification** endpoint that performs a real provider send
- **WebSocket** — live per-server metric and alert/health-change events, JWT-authenticated
- **Audit Logging** — admin-visible log of logins and resource changes
- **Metrics Retention** — background cleanup after `METRIC_RETENTION_DAYS`

## Architecture

```
Dashboard (Streamlit)                 Monitoring Agent (psutil)
        │ REST                                │ REST (+ X-Agent-Token)
        ▼                                     ▼
┌────────────────────────  FastAPI  ────────────────────────┐
│  auth / servers / metrics / alerts / alert-rules          │
│  incidents / notifications / settings / admin / ws        │
│        │                                                  │
│  MonitoringService (health, offline loop, cleanup)        │
│  AlertService (thresholds, dedup, lifecycle)              │
│  NotificationService → Email | WhatsApp | Telegram        │
│  WebSocketManager (per-server broadcast)                  │
└────────────────────────────┬──────────────────────────────┘
                             ▼
                       MongoDB (Beanie ODM)
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, background loop
│   │   ├── config.py                # pydantic-settings (backend/.env)
│   │   ├── database.py              # Motor client + init_beanie
│   │   ├── auth.py                  # re-exports from utils.security
│   │   ├── models/                  # Beanie documents (user, server, metric, alert,
│   │   │                            #   alert_rule, incident, notification,
│   │   │                            #   notification_settings, agent_enrollment,
│   │   │                            #   telegram_connection, audit_log)
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── repositories/            # Data-access layer
│   │   ├── routers/                 # API route modules
│   │   ├── services/                # Business logic + notification providers
│   │   ├── middleware/              # Error handler + request logging
│   │   └── utils/                   # security (JWT/bcrypt), validators, secret masking
│   ├── tests/                       # pytest suite (113 tests)
│   ├── _verify.py                   # static sanity checks (run: python _verify.py)
│   ├── _smoke_test.py               # live smoke test against a running server
│   ├── _e2e_test.py                 # live end-to-end flow test
│   └── requirements.txt
├── frontend/
│   ├── app.py                       # Streamlit shell + login/register
│   ├── api/client.py                # REST client
│   ├── pages/                       # dashboard, servers, server_detail, alerts,
│   │                                #   incidents, notifications, settings
│   └── config.py                    # API_URL from env
├── agent/
│   ├── agent.py                     # enrollment + metric loop with retries
│   ├── config.py                    # API_URL / SERVER_ID / AGENT_TOKEN envs
│   └── collectors/                  # psutil collectors (cpu, memory, disk,
│                                    #   network, system, processes)
├── docker-compose.yml
└── .github/workflows/               # tests.yml (pytest + Mongo service), docker.yml
```

## Quick Start (Docker)

```bash
cp backend/.env.example backend/.env
# edit backend/.env: set SECRET_KEY to a strong random value before exposing anything
docker compose up --build
```

- API: http://localhost:8000 — docs at `/docs`
- Dashboard: http://localhost:8501

Note: inside compose the backend advertises `BACKEND_URL=http://backend:8000`, which is only reachable from the compose network. If agents enroll from machines **outside** the Docker host, set `BACKEND_URL` to the externally reachable URL (e.g. `http://your-host:8000`) via `backend/.env`.

## Local Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows  (source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
cp .env.example .env           # set SECRET_KEY at minimum
uvicorn app.main:app --reload --port 8000
```

Requires MongoDB at `MONGODB_URI` (default `mongodb://localhost:27017`).

### Frontend

```bash
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# API_URL defaults to http://localhost:8000/api; override with env if needed
streamlit run app.py
```

## Windows Client Installer

Clients do **not** need Python, VS Code, Git or any configuration files. The dashboard's **Servers → Install Agent** wizard points them at the official Windows installer:

> **⬇️ Download Windows Agent** → `DevOpsMonitorAgent-Setup.exe` (GitHub Releases)

### Client workflow (no technical steps)

1. **Log in** to the DevOps Monitor Pro dashboard.
2. **Add a server** (Servers → Add Server).
3. **Generate Enrollment Code** (Install Agent wizard) — one-time, valid 20 minutes.
4. **Download the Windows Agent** (`DevOpsMonitorAgent-Setup.exe`).
5. **Run the installer** on the computer/server to monitor.
6. **Paste the enrollment code** when the wizard asks for it and click **Next** — the agent connects to the production backend automatically.
7. **Finish installation** — monitoring starts and (recommended task) restarts automatically after reboots.
8. **Return to the dashboard** — the server shows online with CPU/RAM/disk/health metrics.

Clients never see GitHub, Python commands, `.env` files, server IDs or agent tokens. The permanent agent token returned at enrollment is stored locally in `%ProgramData%\DevOpsMonitorPro\config.json` and is never displayed.

### Building & publishing the installer (maintainers)

1. Set the production API URL in **`agent/build_config.ps1`** (`$ApiUrl = "https://devops-monitor-pro.vercel.app/api"`) — the single centralized build configuration. `http://` and localhost URLs are rejected by the build script.
2. Build locally (needs Windows; installs Inno Setup via `winget install JRSoftware.InnoSetup` for the Setup exe):

```powershell
powershell -ExecutionPolicy Bypass -File agent\build_windows.ps1
```

Outputs (both gitignored):
- `agent/dist/DevOpsMonitorAgent.exe` — portable agent (double-click → enrollment GUI; `--enroll "TOKEN"` from a terminal).
- `agent/dist/DevOpsMonitorAgent-Setup.exe` — **recommended for clients**: install wizard with enrollment-code page, optional start-on-reboot task, clean uninstall.

3. Or let CI build it: pushing a `v*` tag or publishing a release triggers **`.github/workflows/build-agent-release.yml`** (Windows runner) which builds the installer, uploads it as a CI artifact and attaches `DevOpsMonitorAgent-Setup.exe` to the GitHub Release automatically.

### GitHub Release steps

1. Push a tag: `git tag v2.1.0 && git push origin v2.1.0` — CI attaches the installer to the release, **or**
2. Manually: GitHub → Releases → Draft new release → attach `agent/dist/DevOpsMonitorAgent-Setup.exe` → publish.

The dashboard download button points at `https://github.com/Rabiabbasi66/devops-monitor-pro/releases/latest` (override with the `AGENT_DOWNLOAD_URL` env var).

### Developers (source checkout / servers)

The Python agent remains available for development and testing:

```bash
python agent.py --enroll "<ENROLLMENT_TOKEN>"
```

The agent exchanges the token at `POST /api/agents/enroll`, receives its permanent agent token, saves `agent/agent_config.json` (gitignored), and starts sending metrics immediately. Installer headless mode: `DevOpsMonitorAgent.exe --enroll-only "TOKEN" --result-file result.txt` (exit 0/1; never prints the token).

```json
{
  "server_id": "...",
  "agent_token": "...",
  "api_url": "...",
  "interval_seconds": 30
}
```

On later starts the agent loads `agent_config.json` automatically. Without it, set `SERVER_ID` + `AGENT_TOKEN` (e.g. `agent/.env`) — this is also what the Docker agent profile uses.

**Alternative — static token:** creating a server also issues a permanent agent token in the create response, which admins can configure directly (this is what the test suite uses).

### Revoking enrollment tokens

`DELETE /api/agents/{server_id}/enrollment` deletes all unused enrollment tokens for a server.

## Client Workflow (end to end)

1. **Register/Login** — `POST /api/auth/register`, `POST /api/auth/login` (JWT pair).
2. **Add server** — `POST /api/servers/`.
3. **Enroll agent** — wizard or `POST /api/agents/{server_id}/enrollment` → `POST /api/agents/enroll`.
4. **Metrics flow in** — agent `POST /api/monitoring/metrics` with `X-Agent-Token`; server document updates (CPU/RAM/disk/uptime/hostname/agent status) and each sample is stored in the metrics history.
5. **Threshold breach → alert** — e.g. CPU ≥ 95% (critical) creates one alert; repeats inside the cooldown window increment `occurrence_count` instead of duplicating; in-app + external notifications fire per channel settings.
6. **Offline detection** — background loop marks servers with no metrics for `SERVER_OFFLINE_THRESHOLD_SECONDS` offline, raising a critical `connectivity` alert and notifications.
7. **Recovery** — first successful metric ingest after an offline state emits a recovery notification and restores health.
8. **Alert lifecycle** — acknowledge / resolve / reopen via the alerts API; dashboard and server detail views update live over WebSocket.

## Notifications

### Multi-tenant by design

- Provider **infrastructure credentials** (SMTP password, WhatsApp phone-number ID + access token, Telegram bot token) live **only** in platform environment configuration. They are never hard-coded, never stored on user documents, never returned by any API, and are redacted from logs and error messages.
- Clients configure **only their own delivery destination** in **Settings**: email address, WhatsApp number (E.164), or Telegram chat (via one-time connection token — the bot maps `/start <token>` to the user's chat through a webhook).
- Channel documents store only safe metadata (`chat_id`, `telegram_username`); secret-looking keys are stripped before persisting.

### Per-channel settings

| Setting | Values | Effect |
|---|---|---|
| `min_severity` | info, warning, high, critical | Only deliver this severity or higher |
| `notification_types` | alert, recovery, offline, security | Only deliver these event types |
| `cooldown_seconds` | ≥ 0 | Minimum seconds between sends on this channel |
| `enabled` | bool | Master switch |

### Test notifications

`POST /api/notifications/settings/test` performs a **real** send through the selected provider. It validates in order: provider supported → platform enabled → platform configured → recipient valid → provider API result. Errors are specific and secret-free (e.g. "WhatsApp access token is invalid or expired").

### Provider notes

- **Email/Gmail (SMTP)** — set `SMTP_ENABLED=true` plus server/port/sender; for Gmail use an app password. Sends happen in a thread pool so the event loop is never blocked.
- **WhatsApp (Meta Cloud API)** — set `WHATSAPP_ENABLED=true` plus phone-number ID and access token; recipients must be E.164 (e.g. `+923001234567`).
- **Telegram** — set `TELEGRAM_ENABLED=true` and `TELEGRAM_BOT_TOKEN`; optionally `TELEGRAM_WEBHOOK_SECRET` to authenticate webhook calls and `TELEGRAM_BOT_USERNAME` to skip the `getMe` lookup for deep links.

## API Highlights

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me` |
| Servers | `GET/POST /api/servers/`, `GET/PUT/DELETE /api/servers/{id}`, `PUT /api/servers/{id}/thresholds`, `PUT /api/servers/{id}/status` |
| Enrollment | `POST /api/agents/{server_id}/enrollment`, `POST /api/agents/enroll`, `DELETE /api/agents/{server_id}/enrollment` |
| Metrics | `POST /api/monitoring/metrics` (agent), `GET /api/servers/{id}/metrics`, `GET /api/servers/{id}/metrics/latest` |
| Alerts | `GET /api/alerts`, `GET /api/alerts/pending`, `GET/PUT /api/alerts/{id}`, `PUT /api/alerts/{id}/acknowledge|resolve|reopen` |
| Alert rules | `GET/POST /api/alert-rules/`, `GET/PUT/DELETE /api/alert-rules/{id}`, `POST /api/alert-rules/{id}/enable|disable` |
| Incidents | `GET/POST /api/incidents/`, `GET/PUT/DELETE /api/incidents/{id}`, `POST /api/incidents/{id}/acknowledge|resolve|reopen`, `POST /api/incidents/{id}/alerts/{alert_id}` |
| Notifications | `GET /api/notifications`, `PUT /api/notifications/{id}/read`, channels CRUD under `GET/POST /api/notifications/settings`, `PUT/DELETE .../settings/{id}`, `POST .../settings/test` |
| Telegram connect | `POST .../settings/telegram/connect`, `GET .../settings/telegram/connect/status`, `DELETE .../settings/telegram/disconnect`, `POST .../settings/telegram/webhook` (public) |
| Provider status | `GET /api/notifications/settings/providers/status` (booleans only — never credentials) |
| Dashboard | `GET /api/dashboard/summary` |
| WebSocket | `WS /api/ws/servers/{server_id}?token=<JWT>` |
| Health | `GET /health` (DB + background service status) |

## Environment Variables (backend/.env)

| Variable | Description | Default |
|---|---|---|
| MONGODB_URI | MongoDB connection string | `mongodb://localhost:27017` |
| DATABASE_NAME | Database name | `devops_monitor_pro` |
| SECRET_KEY | JWT signing key — **set a strong random value in production** | dev placeholder |
| ALGORITHM | JWT algorithm | `HS256` |
| ACCESS_TOKEN_EXPIRE_MINUTES | Access-token lifetime | `30` |
| REFRESH_TOKEN_EXPIRE_DAYS | Refresh-token lifetime | `7` |
| ENVIRONMENT | `development` / `production` | `development` |
| DEBUG | Verbose logging | `true` |
| ALLOWED_ORIGINS | Extra CORS origins (JSON list) | `["*"]` |
| FRONTEND_URL | CORS origin for the dashboard | `http://localhost:8501` |
| BACKEND_URL | Base URL handed to agents during enrollment | `http://localhost:8000` |
| METRIC_RETENTION_DAYS | Metric cleanup age | `30` |
| ALERT_COOLDOWN_SECONDS | Alert dedup window | `300` |
| SERVER_OFFLINE_THRESHOLD_SECONDS | Offline detection age | `120` |
| HEALTH_CHECK_INTERVAL_SECONDS | Background loop interval | `60` |
| SMTP_ENABLED | Enable email notifications | `false` |
| SMTP_SERVER / SMTP_PORT / SMTP_USE_TLS | SMTP transport | `smtp.gmail.com` / `587` / `true` |
| SMTP_USERNAME / SMTP_PASSWORD | Platform SMTP credentials | empty |
| SMTP_FROM_EMAIL / SMTP_FROM_NAME | Sender identity | empty / `DevOps Monitor Pro` |
| WHATSAPP_ENABLED | Enable WhatsApp notifications | `false` |
| WHATSAPP_API_URL | Meta Graph API base | `https://graph.facebook.com/v17.0` |
| WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN | Platform WhatsApp sender | empty |
| WHATSAPP_TIMEOUT | Request timeout (s) | `30` |
| TELEGRAM_ENABLED | Enable Telegram notifications | `false` |
| TELEGRAM_BOT_TOKEN | Platform bot token | empty |
| TELEGRAM_TIMEOUT / TELEGRAM_PARSE_MODE | Bot API options | `30` / `HTML` |
| TELEGRAM_BOT_USERNAME | Optional static bot username (skips getMe) | empty |
| TELEGRAM_WEBHOOK_SECRET | Shared secret for webhook verification | empty |
| TELEGRAM_CONNECT_TOKEN_EXPIRE_MINUTES | One-time connect token lifetime | `15` |

Agent env (`agent/.env` or enrollment): `API_URL`, `SERVER_ID`, `AGENT_TOKEN`, `INTERVAL_SECONDS`.
Frontend env: `API_URL` (default `http://localhost:8000/api`).

## Testing

```bash
cd backend
pytest -q
```

Requires MongoDB on `MONGODB_URI` (defaults to `localhost:27017`); tests use the `devops_monitor_pro_test` database and run against the real app via ASGI transport with lifespan initialisation. CI (`.github/workflows/tests.yml`) runs the same suite with a Mongo service container.

**Current result: 113 passed.**

Coverage includes: auth + refresh-token type enforcement, server CRUD and ownership, enrollment token lifecycle (expiry, single-use, wrong-owner), metric ingestion contract (server fields updated, history stored, unknown fields ignored, bad token → 401), alert lifecycle (dedup/cooldown/occurrences/ack/resolve/reopen/separate metric types), alert rules CRUD + ownership, incidents, dashboard summary shape, notification providers (enablement, missing-config errors, secret-free responses/logs, error mapping, failure isolation), channel ownership, cooldown/severity/type filtering, Telegram connect tokens (randomness, hashing, expiry, single-use, ownership) and webhook secret verification.

### Live verification helpers (optional)

With a server running on port 8021 (or edit `BASE` in each script):

```bash
cd backend
uvicorn app.main:app --port 8021 &
python _verify.py       # static checks (imports, query expressions, provider payload)
python _smoke_test.py   # HTTP smoke test (20 checks)
python _e2e_test.py     # full flow: login → server → enroll → metrics → alert → recovery (22 checks)
```

## Deployment

1. **Secrets** — generate a strong `SECRET_KEY` (32+ random chars); never commit `.env` or `agent_config.json` (both gitignored). Do not put real credentials in source or docs.
2. **Database** — point `MONGODB_URI` at a production MongoDB (replica set recommended); do not expose Mongo publicly.
3. **CORS** — set `ENVIRONMENT=production`, `FRONTEND_URL` to the dashboard origin, and restrict `ALLOWED_ORIGINS` (never `["*"]`).
4. **Agent URL** — set `BACKEND_URL` to the externally reachable API base used in enrollment commands.
5. **Notifications** — configure platform provider credentials via environment; clients then connect their own recipients in Settings.
6. **Run** — `docker compose up -d`, or manually: `uvicorn app.main:app --host 0.0.0.0 --port 8000` behind a reverse proxy with TLS, `streamlit run app.py --server.port 8501`, and agents enrolled per machine.
7. **Operations** — the background loop handles offline detection and metric retention; `GET /health` exposes DB + service status for load-balancer probes; logs are structured and secret-masked.

## Security Model

- bcrypt (rounds 12, 72-byte truncation-safe) password hashing; password strength validated at registration
- JWT access (30 min) + refresh (7 days) tokens; refresh endpoint rejects access tokens by `type` claim
- Every user-scoped route filters by owner; admins see all; ownership violations return 404 (no enumeration)
- Agent auth via `X-Agent-Token` bound to one server; tokens from server A cannot ingest for server B (401)
- Enrollment + Telegram connect tokens: cryptographically random, SHA-256 hashed at rest, expiring, single-use
- Provider credentials: environment-only, redacted from logs/errors, stripped from user documents, never in API responses
- Telegram webhook verifies `X-Telegram-Bot-Api-Secret-Token` when configured (constant-time compare)
- `agent_config.json`, `.env` gitignored

## Troubleshooting

- **Enrollment fails** — token expired (20 min) or already used; generate a new one. Verify `BACKEND_URL` is reachable from the agent machine.
- **Metrics rejected (401)** — agent token doesn't match the server (or monitoring disabled); re-enroll or re-issue.
- **Server shows offline** — no metrics within `SERVER_OFFLINE_THRESHOLD_SECONDS`; check the agent process/logs.
- **No notifications** — check `GET /api/notifications/settings/providers/status` (platform config), then the channel's `enabled`, `min_severity`, `notification_types` and `cooldown_seconds`.
- **Email auth errors** — Gmail requires an app password; verify `SMTP_USERNAME`/`SMTP_PASSWORD`.
- **Telegram deep link missing** — bot token invalid or `getMe` unreachable; set `TELEGRAM_BOT_USERNAME` to skip the lookup.
- **WebSocket closes immediately (1008/403)** — the `token` query parameter must be a valid access JWT.

## Future Improvements

- Scheduled alert-rule evaluation engine (rules currently provide per-user threshold config; runtime evaluation follows server thresholds)
- Hourly/daily metric rollups for long-range charts
- Rate-limiting middleware (settings exist; enforcement pending)
- Prometheus exporter
- Slack/webhook providers
- Historical alert analytics
