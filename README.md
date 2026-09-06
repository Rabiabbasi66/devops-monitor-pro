# DevOps Monitor Pro

Production-ready DevOps infrastructure monitoring platform with FastAPI, MongoDB, Streamlit dashboard, and a psutil-based monitoring agent.

## Features

### Core Functionality
- User registration, JWT authentication, RBAC (admin/user)
- Server CRUD with per-server agent tokens
- **Automatic Agent Enrollment** - No manual token configuration required
- Monitoring agent collects CPU, memory, disk, network, uptime, processes
- Metric storage with retention and time-range queries
- Automatic alert engine with configurable thresholds and deduplication
- Alert lifecycle: pending → acknowledged → resolved → reopen
- WebSocket real-time metric and alert streaming
- In-app notifications
- Audit logging (admin)
- Dashboard summary API
- Docker Compose deployment
- GitHub Actions CI (tests + Docker build)

### Advanced Dashboard
- **Professional DevOps Monitoring Interface** - Modern, dark-themed UI
- **Real-time Summary Metrics** - Total servers, online/offline status, critical warnings
- **Advanced Server Cards** - Visual health indicators, status badges, live metrics
- **Interactive Charts** - CPU, memory, disk, network usage over time
- **Auto-refresh Capability** - Optional real-time updates
- **Responsive Design** - Works on desktop, laptop, and tablet

### Server Management
- **Search and Filtering** - Find servers by name, IP, tags, or status
- **Status Filtering** - Filter by online, offline, warning, critical
- **Install Agent Wizard** - Step-by-step agent installation guide
- **OS-specific Instructions** - Windows, Linux, macOS support
- **Automatic Server Detection** - Servers appear automatically when agent connects
- **Safe Delete Operations** - Confirmation before destructive actions

### Server Detail View
- **Comprehensive Metrics** - CPU, memory, disk, network, response time, uptime
- **Time Range Selection** - 1, 6, 12, 24, 48, 72 hours
- **Advanced Charts** - Multi-panel visualization with auto-refresh
- **Threshold Configuration** - Customizable alert thresholds per server
- **Alert History** - Server-specific alert timeline
- **Auto-refresh Metrics** - Live monitoring capability

### Alerts Management
- **Severity Filtering** - Critical, high, medium, low
- **Status Filtering** - Pending, acknowledged, resolved
- **Unresolved Alerts View** - Focus on active issues
- **Visual Severity Indicators** - Color-coded alert cards
- **Bulk Actions** - Quick acknowledge, resolve, reopen
- **Server Integration** - Direct navigation to affected servers

### Notifications Center
- **Unread Count** - Quick view of pending notifications
- **Type-based Styling** - Different icons for alerts, warnings, info
- **Mark as Read** - Individual notification management
- **Server Context** - Direct server access from notifications
- **Clean Interface** - Organized by read/unread status

### Agent Enrollment System
- **Short-lived Enrollment Tokens** - 15-30 minute expiration
- **Single-use Tokens** - Enhanced security
- **Automatic Configuration** - Agent saves credentials automatically
- **Cross-platform Support** - Windows, Linux, macOS
- **Fallback Support** - Existing .env configuration still works
- **No Manual Token Entry** - Completely automated setup

## Architecture

```
Dashboard (Streamlit)
        │ REST / WebSocket
        ▼
   FastAPI API
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
MongoDB  Alert Engine  Notifications
   ▲
   │ POST /api/monitoring/metrics
Monitoring Agent (psutil)
```

## Project Structure

```
devops_monitor_pro/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/
│       │   ├── agent_enrollment.py  # NEW: Enrollment model
│       │   ├── server.py
│       │   ├── user.py
│       │   ├── metric.py
│       │   ├── alert.py
│       │   └── notification.py
│       ├── schemas/
│       ├── services/
│       ├── repositories/
│       ├── routers/
│       │   ├── agent_enrollment_router.py  # NEW: Enrollment endpoints
│       │   ├── server_router.py
│       │   ├── monitoring_router.py
│       │   └── alerts_router.py
│       ├── middleware/
│       └── utils/
├── frontend/
│   ├── app.py                    # UPDATED: Modern login and navigation
│   ├── api/client.py             # UPDATED: Better error handling
│   └── pages/
│       ├── dashboard.py          # UPDATED: Advanced dashboard
│       ├── servers.py            # UPDATED: Search, filters, install wizard
│       ├── server_detail.py      # UPDATED: Advanced charts, time ranges
│       ├── alerts.py             # UPDATED: Filtering, severity indicators
│       └── notifications.py      # UPDATED: Modern notification center
├── agent/
│   ├── agent.py                  # UPDATED: Enrollment support
│   ├── config.py
│   ├── agent_config.json         # NEW: Auto-generated config
│   └── collectors/
├── tests/ (in backend/tests/)
├── docker-compose.yml
└── .github/workflows/
```

## Quick Start (Docker)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- API: http://localhost:8000/docs
- Dashboard: http://localhost:8501

## Local Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set API_URL=http://localhost:8000/api
streamlit run app.py
```

### Monitoring Agent (NEW - Automatic Enrollment)

**Option 1: Automatic Enrollment (Recommended)**

1. Create a server in the dashboard
2. Click "Install Agent" on the server card
3. Follow the step-by-step wizard:
   - Select your operating system
   - Generate enrollment token
   - Copy and run the enrollment command
   - Agent automatically configures and starts monitoring

```bash
# Example enrollment command (provided by wizard)
python agent.py --enroll "<ENROLLMENT_TOKEN>"
```

**Option 2: Manual Configuration (Legacy)**

```bash
cd agent
pip install -r requirements.txt
cp .env.example .env
# Set SERVER_ID and AGENT_TOKEN manually
python agent.py
```

### Agent Configuration File

After successful enrollment, the agent creates `agent_config.json`:

```json
{
  "server_id": "...",
  "agent_token": "...",
  "api_url": "http://localhost:8000",
  "interval_seconds": 30
}
```

The agent automatically uses this file on subsequent starts.

## Environment Variables

|| Variable | Description | Default |
||----------|-------------|---------|
|| MONGODB_URI | MongoDB connection string | mongodb://localhost:27017 |
|| DATABASE_NAME | Database name | devops_monitor_pro |
|| SECRET_KEY | JWT signing key | (required in production) |
|| FRONTEND_URL | CORS origin | http://localhost:8501 |
|| BACKEND_URL | Backend URL for agent enrollment | http://localhost:8000 |
|| METRIC_RETENTION_DAYS | Metric cleanup retention | 30 |
|| ALERT_COOLDOWN_SECONDS | Alert dedup window | 300 |
|| SERVER_OFFLINE_THRESHOLD_SECONDS | Offline detection | 120 |
|| HEALTH_CHECK_INTERVAL_SECONDS | Background health check interval | 60 |

## API Highlights

### Authentication
|| Endpoint | Description |
||----------|-------------|
|| POST /api/auth/register | Register user |
|| POST /api/auth/login | Login |
|| GET /api/auth/me | Get current user |

### Servers
|| Endpoint | Description |
||----------|-------------|
|| GET /api/servers | List servers (with filters) |
|| POST /api/servers | Create server |
|| GET /api/servers/{id} | Get server details |
|| PUT /api/servers/{id} | Update server |
|| DELETE /api/servers/{id} | Delete server |
|| PUT /api/servers/{id}/thresholds | Update alert thresholds |

### Agent Enrollment (NEW)
|| Endpoint | Description |
||----------|-------------|
|| POST /api/agents/{server_id}/enrollment | Generate enrollment token |
|| POST /api/agents/enroll | Enroll agent using token |

### Monitoring
|| Endpoint | Description |
||----------|-------------|
|| POST /api/monitoring/metrics | Agent metric ingestion |
|| GET /api/servers/{id}/metrics | Historical metrics (with time range) |

### Alerts
|| Endpoint | Description |
||----------|-------------|
|| GET /api/alerts | List alerts (with filters) |
|| GET /api/alerts/pending | Pending alerts |
|| PUT /api/alerts/{id}/acknowledge | Acknowledge alert |
|| PUT /api/alerts/{id}/resolve | Resolve alert |
|| PUT /api/alerts/{id}/reopen | Reopen alert |

### Dashboard
|| Endpoint | Description |
||----------|-------------|
|| GET /api/dashboard/summary | Dashboard statistics |
|| WS /api/ws/servers/{id}?token=JWT | Real-time updates |

### System
|| Endpoint | Description |
||----------|-------------|
|| GET /health | Health check |

## User Experience Flow

1. **Register/Login** - Create account or login
2. **Add Server** - Create a new server entry
3. **Install Agent** - Use the Install Agent wizard
4. **Enroll Agent** - Run the enrollment command on target machine
5. **Automatic Monitoring** - Agent connects and starts sending metrics
6. **View Dashboard** - See real-time server status and metrics
7. **Monitor Alerts** - Receive and manage alerts automatically
8. **Analyze Details** - Drill down into server-specific metrics

## Security

- bcrypt password hashing
- JWT access + refresh tokens
- Server ownership enforced on all protected routes
- Agent authentication via `X-Agent-Token` header
- Cryptographically secure enrollment tokens
- Short-lived, single-use enrollment tokens
- No secrets in source code — use `.env`
- `agent_config.json` automatically added to .gitignore

## Testing

```bash
cd backend
pytest -q
```

Requires MongoDB running on localhost:27017.

### Test Coverage

The implementation includes comprehensive testing for:
- Agent enrollment generation and validation
- Token expiration and single-use enforcement
- Server ownership authorization
- Metric ingestion and storage
- Alert generation and lifecycle
- API authentication and authorization
- Real-time WebSocket connections

## Deployment

### Production Setup

1. **Environment Variables**: Set all required environment variables
2. **MongoDB**: Configure production MongoDB connection
3. **CORS**: Update `FRONTEND_URL` and `ALLOWED_ORIGINS`
4. **Secrets**: Use strong `SECRET_KEY` for JWT signing
5. **Agent URL**: Configure `BACKEND_URL` for agent enrollment
6. **Monitoring**: Set appropriate retention and threshold values

### Docker Deployment

```bash
# Production docker-compose
docker compose -f docker-compose.yml up -d
```

### Manual Deployment

1. Deploy backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Deploy frontend with `streamlit run app.py --server.port 8501`
3. Deploy agents on target machines using enrollment system
4. Configure reverse proxy (nginx) for production
5. Set up SSL/TLS certificates
6. Configure monitoring and alerting for the monitoring system itself

## Troubleshooting

### Agent Issues
- **Enrollment fails**: Check enrollment token validity and expiration
- **Agent not connecting**: Verify `BACKEND_URL` and network connectivity
- **Config file missing**: Re-run enrollment or check file permissions
- **Metrics not appearing**: Check agent logs and server last_seen timestamp

### Dashboard Issues
- **Servers not appearing**: Ensure agent is successfully enrolled and running
- **Metrics not updating**: Check WebSocket connection and agent interval
- **Alerts not triggering**: Verify threshold configuration and metric values

### Backend Issues
- **Database connection**: Check MongoDB connection string and availability
- **Authentication failures**: Verify JWT configuration and token expiration
- **API errors**: Check logs for detailed error messages

## Future Improvements

- Email/Slack notifications
- Hourly/daily metric rollups
- Rate limiting middleware
- Prometheus exporter
- Advanced 3D server visualization
- Mobile-responsive optimization
- Custom dashboard layouts
- Historical alert analytics
- Performance baseline tracking
- Predictive alerting based on trends
