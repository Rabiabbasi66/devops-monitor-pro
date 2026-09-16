# DevOps Monitor Pro

DevOps Monitor Pro is a production-ready infrastructure monitoring platform. A **FastAPI + MongoDB** backend collects metrics from lightweight monitoring agents installed on Windows servers, and a **Streamlit web dashboard** lets you and your clients monitor every server in real time: CPU, memory, disk, alerts, incidents and email (Gmail) notifications.

- **Backend (API):** FastAPI + MongoDB (Beanie ODM) - deployed on Vercel
- **Web Dashboard:** Streamlit - deployed on Streamlit Cloud
- **Monitoring Agent:** Python/psutil packaged as a Windows installer (PyInstaller + Inno Setup) - distributed via GitHub Releases
- **Notifications:** Gmail/email (platform-managed SMTP) with a verified-recipient flow

All documented features are covered by the backend test suite (`backend/tests/`, 83 tests, also executed in CI against a real MongoDB service).

## Key Features

- **User accounts** - registration, login, JWT access + refresh tokens, bcrypt password hashing, admin/user roles
- **Server management** - add/edit/delete servers, per-server alert thresholds, environment and tag metadata, monitoring enable/disable
- **Automatic agent enrollment** - one-time enrollment code from the dashboard; no manual token configuration for clients
- **Continuous monitoring** - CPU, memory, disk, network, uptime, system info and top processes every 30 seconds
- **Health states** - Healthy / Warning / Critical / Offline / Unknown calculated from thresholds and last-seen age
- **Alert engine** - threshold evaluation on every metric ingest, occurrence counting instead of duplicate alerts, acknowledge/resolve/reopen lifecycle
- **Offline detection and recovery** - background loop marks silent servers offline, raises connectivity alerts and emits recovery notifications
- **Incident management** - group related alerts into incidents with their own lifecycle
- **Email (Gmail) notifications** - verified recipient addresses, severity filtering, event-type filtering and cooldown windows
- **Real-time dashboard** - live metric and alert updates over WebSocket
- **Audit logging** - admin-visible log of logins and resource changes
- **Mobile-friendly dashboard** - responsive layout that works on phones and tablets

> Note: WhatsApp and Telegram channels from earlier builds are **not** part of the current production flow. The production notification channel is email (Gmail/SMTP) only.

## Architecture

```
  Windows Agent (psutil, 30s loop)          Web Dashboard (Streamlit)
        |                                        |
        |  POST /api/monitoring/metrics          |  REST + WebSocket (JWT)
        |  header: X-Agent-Token                 |
        v                                        v
  +-------------------------------------------------+
  |              FastAPI Backend (Vercel)           |
  |  auth | servers | metrics | alerts | incidents  |
  |  notifications | settings | admin | ws          |
  |  MonitoringService (health, offline loop)       |
  |  AlertService (thresholds, dedup, lifecycle)    |
  |  NotificationService -> Email (SMTP/Gmail)      |
  +-------------------------------------------------+
                          |
                    MongoDB (Beanie ODM)
```

## Production Deployment

| Component | URL | Notes |
|---|---|---|
| Backend API | `https://devops-monitor-pro.vercel.app` | FastAPI on Vercel; REST base is `/api`; Swagger docs at `/docs` |
| Health check | `https://devops-monitor-pro.vercel.app/health` | Returns `status: healthy`, `database: connected`, `monitoring_service: running` |
| Web Dashboard | Streamlit Cloud app | Deployed via share.streamlit.io; linked from the repository "About" section |
| Windows Agent installer | `https://github.com/Rabiabbasi66/devops-monitor-pro/releases/latest/download/DevOpsMonitorAgent-Setup.exe` | Attached to the latest GitHub Release |

The dashboard resolves its API base in this order: `st.secrets["API_URL"]` -> `API_URL` environment variable -> the built-in production default `https://devops-monitor-pro.vercel.app/api` (`frontend/config.py`). The Windows agent ships with the same production URL baked in at build time (`agent/build_config.ps1`).

## Web Dashboard

The Streamlit dashboard is the single place clients interact with:

- **Login / Register** page with JWT-backed sessions
- **Dashboard** page - summary cards (total servers, online, critical), per-server cards with health icon and CPU/RAM/disk bars, live WebSocket updates
- **Servers** page - add/edit/remove servers and run the **Install Agent** wizard
- **Server detail** - live charts, metric history, recent alerts, top processes
- **Alerts** page - acknowledge, resolve and reopen alerts
- **Incidents** page - group and track related alerts
- **Settings** page - email notification setup, Gmail verification, test email, admin audit logs and users

## Server and Agent Monitoring

1. Add a server in the dashboard (**Servers -> Add Server**).
2. Open the **Install Agent** wizard - it generates a **one-time enrollment code** (valid 20 minutes, single-use).
3. Download and run the Windows installer on the server to be monitored.
4. Paste the enrollment code into the installer wizard. The agent exchanges it at `POST /api/agents/enroll` for a permanent agent token.
5. The token is stored locally in `%ProgramData%\DevOpsMonitorPro\config.json` - it is never displayed to the client.
6. The agent reports metrics every 30 seconds via `POST /api/monitoring/metrics` with its `X-Agent-Token` header.
7. If no metrics arrive within `SERVER_OFFLINE_THRESHOLD_SECONDS` (default 120), the server is marked **Offline** and a critical connectivity alert is raised. The next successful report emits a **recovery** notification.

Enrollment tokens are cryptographically random, SHA-256 hashed at rest, expiring and single-use. Agent tokens are bound to exactly one server - a token from server A cannot ingest metrics for server B.

## Metrics Collected

The agent (psutil-based collectors) reports:

- **CPU** - total and per-core utilization, load average
- **Memory** - total/used/percent plus swap
- **Disk** - per-partition usage plus disk I/O counters
- **Network** - traffic counters and packet stats
- **System** - hostname, OS, boot time/uptime
- **Processes** - top CPU and memory consumers

Each server stores a time-series metric history (retention controlled by `METRIC_RETENTION_DAYS`, default 30) with aggregation support for charts. Health is computed as Healthy / Warning / Critical / Offline / Unknown from per-server thresholds.

## Alerts and Incidents

- **Threshold alerts** - every metric ingest is evaluated against the per-metric thresholds of each server; a breach opens one alert. Repeats inside the cooldown window increment the alert `occurrence_count` instead of creating duplicates.
- **Alert lifecycle** - acknowledge, resolve, reopen. Dashboard and server views update live over WebSocket.
- **Connectivity alerts** - offline servers raise a critical `connectivity` alert automatically.
- **Recovery notifications** - the first successful ingest after an offline period restores health and notifies the user.
- **Incidents** - related alerts are grouped into incidents with acknowledge/resolve/reopen and ownership enforcement.

## Gmail and Email Notifications

Production notifications are **email only** (in-app notifications are always available in the dashboard). SMTP credentials are managed by the platform - clients only provide the destination address.

### Client configuration flow

1. Open **Settings -> Email Notifications**.
2. Enter the Gmail address that should receive alerts.
3. Click **Send verification code** - the platform emails a 6-digit code.
4. Enter the code within 10 minutes and click **Verify Email**. The address is now trusted.
5. Save the channel settings: minimum severity (`info` / `warning` / `high` / `critical`), notification types (`alert` / `recovery` / `offline`) and cooldown seconds.
6. Click **Test** to receive a real test email.

### How verification works

- The 6-digit code is generated with a cryptographically secure random generator.
- Only a **SHA-256 hash** of the code is stored; the plain code is never persisted.
- Codes expire after 10 minutes and are **single-use**.
- Requesting a new code invalidates the previous one.
- Verification state is stored per user + email address; unverified addresses never receive alerts.

### Alert email contents

Alert emails include the server name, metric, measured value vs threshold, severity, occurrence count and a timestamp, plus recovery/offline notices for the matching event types.

## Windows Agent (Installer)

Clients do not need Python, Git, VS Code or any configuration files. The dashboard **Servers -> Install Agent** wizard points them at the official Windows installer:

> **Download Windows Agent** - `DevOpsMonitorAgent-Setup.exe` (GitHub Releases)

The installer provides:

- A setup wizard with an **enrollment-code page** (no server IDs or agent tokens exposed)
- Automatic configuration of the production API URL (baked in at build time)
- Optional **start-on-reboot** task so monitoring resumes after restarts
- Automatic reconnection if the network or API is temporarily unavailable
- Clean uninstall support (removes the service, task and local config)

Credentials after enrollment live in `%ProgramData%\DevOpsMonitorPro\config.json` (restricted permissions, written atomically). The permanent agent token is never displayed, logged or emailed.

### Client workflow (end to end)

1. **Register / Log in** to the dashboard.
2. **Add a server** (Servers -> Add Server).
3. **Generate enrollment code** (Install Agent wizard) - one-time, valid 20 minutes.
4. **Download the Windows Agent** installer.
5. **Run the installer as Administrator** on the machine to monitor.
6. **Paste the enrollment code** when asked and click Next - the agent connects to the production backend automatically.
7. **Finish** - monitoring starts immediately and resumes after reboots.
8. **Return to the dashboard** - the server appears online with CPU/RAM/disk metrics.
9. **Configure Gmail** (Settings -> Email Notifications) and verify with the emailed code to start receiving alert emails.

## Installation and Downloads

### Clients (recommended)

Download the latest Windows installer and follow the wizard:

```
https://github.com/Rabiabbasi66/devops-monitor-pro/releases/latest/download/DevOpsMonitorAgent-Setup.exe
```

Current pinned release (v2.1.2):

```
https://github.com/Rabiabbasi66/devops-monitor-pro/releases/download/v2.1.2/DevOpsMonitorAgent-Setup.exe
```

Requirements: Windows 10 or 11, internet access, and a valid enrollment code from the dashboard.

### Developers (source checkout)

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Requires a MongoDB instance at `MONGODB_URI` (default `mongodb://localhost:27017`).

### Docker

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- API: `http://localhost:8000` (docs at `/docs`)
- Dashboard: `http://localhost:8501`
- Optional agent container: `docker compose --profile agent up -d` with `SERVER_ID` + `AGENT_TOKEN`

## GitHub Releases

The Windows agent installer is distributed exclusively through GitHub Releases - it is never committed to the repository.

| Release | Tag | Date | Status |
|---|---|---|---|
| DevOps Monitor Pro | `v2.1.0` | 2026-09-14 | Superseded - first installer release |
| v2.1.1 | `v2.1.1` | 2026-09-14 | Superseded - installer build fix |
| **v2.1.2** | `v2.1.2` | 2026-09-14 | **Latest production release** - enrollment + installer runtime fix |

Each release ships `DevOpsMonitorAgent-Setup.exe` (plus source archives). The next planned release is the final production release **v1.0.0**; pushing a `v*` tag automatically builds the installer and attaches it to the release.

## Building and Publishing the Installer (maintainers)

1. Set the production API URL in **`agent/build_config.ps1`** (`$ApiUrl = "https://devops-monitor-pro.vercel.app/api"`). The build refuses `http://` and localhost URLs so an insecure URL can never ship to clients.
2. Build locally (Windows + Inno Setup: `winget install JRSoftware.InnoSetup`):

```powershell
powershell -ExecutionPolicy Bypass -File agent\build_windows.ps1
```

Outputs (gitignored):

- `agent/dist/DevOpsMonitorAgent.exe` - portable agent (double-click opens the enrollment GUI)
- `agent/dist/DevOpsMonitorAgent-Setup.exe` - recommended for clients

3. Or let CI build it: pushing a `v*` tag or publishing a release triggers `.github/workflows/build-agent-release.yml` (Windows runner), which builds the installer, uploads it as a CI artifact and attaches `DevOpsMonitorAgent-Setup.exe` to the GitHub Release.

Release steps: `git tag v1.0.0 && git push origin v1.0.0`, then create/publish the release on GitHub for the tag - CI attaches the installer automatically.

## Continuous Integration

| Workflow | Trigger | What it does |
|---|---|---|
| **Tests** (`.github/workflows/tests.yml`) | push/PR on main | Installs backend deps, starts a MongoDB 7 service, runs the pytest suite (83 tests) |
| **Docker Build** (`.github/workflows/docker.yml`) | push/PR on main | Builds the backend and frontend Docker images |
| **Build Agent Release** (`.github/workflows/build-agent-release.yml`) | `v*` tags / release published | Builds the portable agent + Windows installer and attaches it to the release |

All three workflows are green on the current `main` branch.

## Project Structure

```
+-- backend/
|   +-- app/
|   |   +-- main.py                  # FastAPI app, lifespan, background loop
|   |   +-- config.py                # pydantic-settings (backend/.env)
|   |   +-- database.py              # Motor client + init_beanie
|   |   +-- models/                  # Beanie documents (user, server, metric, alert,
|   |   |                            #   alert_rule, incident, notification,
|   |   |                            #   notification_settings, email_verification)
|   |   +-- schemas/                 # Pydantic request/response models
|   |   +-- repositories/            # Data-access layer
|   |   +-- routers/                 # API route modules
|   |   +-- services/                # Business logic + email provider
|   |   +-- middleware/              # Error handler + request logging
|   |   +-- utils/                   # security (JWT/bcrypt), validators, secret masking
|   +-- tests/                       # pytest suite (83 tests)
|   +-- Dockerfile
|   +-- requirements.txt
+-- frontend/
|   +-- app.py                       # Streamlit shell + login/register
|   +-- api/client.py                # REST client (API_URL resolution)
|   +-- pages/                       # dashboard, servers, server_detail, alerts,
|   |                                #   incidents, settings
|   +-- config.py                    # production API URL default + overrides
|   +-- runtime.txt                  # Streamlit Cloud Python version
+-- agent/
|   +-- agent.py                     # enrollment + metric loop with retries
|   +-- gui.py                       # enrollment GUI for the packaged agent
|   +-- collectors/                  # psutil collectors (cpu, memory, disk, network,
|   |                                #   system, processes)
|   +-- credentials_file.py          # secure local storage of agent credentials
|   +-- build_config.ps1             # ONE place to set the production API URL + version
|   +-- build_windows.ps1            # PyInstaller + Inno Setup build script
|   +-- installer/DevOpsMonitorAgent.iss
|   +-- DevOpsMonitorAgent.spec
|   +-- Dockerfile
+-- docs/
|   +-- CLIENT_GUIDE.md              # client-facing installation guide
+-- .github/workflows/               # tests.yml, docker.yml, build-agent-release.yml
+-- docker-compose.yml
+-- README.md
```

## Technologies Used

- **Backend:** Python 3.11, FastAPI, Uvicorn, MongoDB + Beanie (Motor), Pydantic/pydantic-settings, Passlib bcrypt, PyJWT, WebSockets
- **Frontend:** Streamlit, Requests, python-dotenv
- **Agent:** Python, psutil, Requests, PyInstaller, Inno Setup 6 (Windows installer)
- **Database:** MongoDB (replica set recommended in production)
- **Deployment:** Vercel (API), Streamlit Cloud (dashboard), Docker / docker-compose (self-hosting)
- **CI/CD:** GitHub Actions (tests with MongoDB service, Docker build, agent release pipeline)

## Troubleshooting

- **Enrollment fails** - the code expired (20 minutes) or was already used; generate a new one from the Install Agent wizard. Confirm the machine can reach `https://devops-monitor-pro.vercel.app`.
- **Metrics rejected (401)** - the agent token does not match the server or monitoring was disabled; re-enroll the agent.
- **Server shows Offline** - no metrics within `SERVER_OFFLINE_THRESHOLD_SECONDS`; check the agent service is running on the machine.
- **No alert emails** - confirm the email address is **verified** (Settings), the channel is enabled, `min_severity` is not too high, and the event type (alert/recovery/offline) is selected. Check the platform SMTP status via `GET /api/notifications/settings/providers/status`.
- **Email auth errors (admin)** - Gmail requires an app password for SMTP; verify `SMTP_USERNAME`/`SMTP_PASSWORD` in the platform environment.
- **Verification code rejected** - codes expire after 10 minutes and are single-use; request a fresh code.
- **Dashboard page blank / API errors** - confirm `https://devops-monitor-pro.vercel.app/health` returns healthy, then re-open the dashboard.
- **WebSocket closes immediately (1008/403)** - the `token` query parameter must be a valid access JWT.

## Security Notes

- bcrypt password hashing (rounds 12, 72-byte truncation-safe); password strength validated at registration
- JWT access (30 min) + refresh (7 days) tokens; refresh endpoint rejects access tokens by `type` claim
- Every user-scoped route filters by owner; admins see all; ownership violations return 404 (no resource enumeration)
- Agent auth via `X-Agent-Token` bound to one server; cross-server ingestion returns 401
- Enrollment and email-verification codes: cryptographically random, SHA-256 hashed at rest, expiring, single-use
- SMTP credentials are platform-only (environment variables), redacted from logs/errors, never returned by the API and never stored on user documents
- `backend/.env`, `agent/agent_config.json` and build artifacts are gitignored - never commit secrets
- Client builds always use HTTPS; the agent build script rejects `http://` and localhost API URLs

## Author

**Fazal-E- Rabbi Abbasi** - [GitHub: @Rabiabbasi66](https://github.com/Rabiabbasi66)

- Repository: <https://github.com/Rabiabbasi66/devops-monitor-pro>
- Live API: <https://devops-monitor-pro.vercel.app>
- Client guide: [docs/CLIENT_GUIDE.md](docs/CLIENT_GUIDE.md)
