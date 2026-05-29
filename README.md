# QuantumFence

![CI/CD Status](https://img.shields.io/github/actions/workflow/status/quantsingularity/QuantumFence/cicd.yml?branch=main&label=CI/CD&logo=github)
[![Test Coverage](https://img.shields.io/badge/coverage-85%25-green)](https://github.com/quantsingularity/QuantumFence/tree/main/tests)
[![License](https://img.shields.io/github/license/quantsingularity/AlphaMind)](https://github.com/quantsingularity/QuantumFence/blob/main/LICENSE)

### Quantum-Accelerated Perimeter Defense AI System

> **AI-powered multi-camera perimeter security with real-time drone detection, geofencing, and Claude AI threat analysis.**

---

## Project Structure

```
QuantumFence/
├── code/
│   ├── backend/                  # FastAPI Python backend
│   │   ├── main.py               # Application entry point
│   │   ├── config/
│   │   │   └── settings.py       # All system configuration
│   │   ├── api/
│   │   │   ├── routes/           # REST API endpoints
│   │   │   │   ├── auth.py       # JWT authentication
│   │   │   │   ├── cameras.py    # Camera CRUD + management
│   │   │   │   ├── alerts.py     # Alert management
│   │   │   │   ├── drones.py     # Drone detections
│   │   │   │   ├── analytics.py  # Analytics & reporting
│   │   │   │   └── geofences.py  # Geofence zones
│   │   │   └── websocket.py      # Real-time WebSocket hub
│   │   ├── database/
│   │   │   ├── database.py       # SQLAlchemy engine & session
│   │   │   └── models.py         # All ORM models
│   │   ├── services/
│   │   │   ├── detection_service.py      # Camera processing orchestrator
│   │   │   ├── ai_analysis_service.py    # Claude AI threat analysis
│   │   │   ├── notification_service.py   # Email & webhook alerts
│   │   │   └── perimeter_service.py      # Fence breach intelligence
│   │   └── requirements.txt
│   ├── ai_models/
│   │   ├── model_manager.py      # YOLOv8 model loader & runner
│   │   └── drone_detector.py     # Drone tracking & trajectory analysis
│   └── integrations/
│       └── google_earth.py       # Google Maps/Earth KML/API
├── web-frontend/                 # React + Vite SPA
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx     # Live command center
│   │   │   ├── Cameras.jsx       # Camera management
│   │   │   ├── Alerts.jsx        # Alert management table
│   │   │   ├── DroneWatch.jsx    # Drone radar & log
│   │   │   ├── MapView.jsx       # Leaflet tactical map
│   │   │   ├── Analytics.jsx     # Charts & reporting
│   │   │   ├── Settings.jsx      # System configuration
│   │   │   └── Login.jsx         # Authentication
│   │   ├── components/
│   │   │   └── Layout.jsx        # Sidebar navigation
│   │   ├── context/
│   │   │   ├── AuthContext.jsx   # JWT auth state
│   │   │   └── WebSocketContext.jsx  # Real-time events
│   │   └── services/
│   │       └── api.js            # Axios API client
├── infrastructure/
│   ├── docker/
│   │   ├── docker-compose.yml    # Full stack deployment
│   │   ├── Dockerfile.backend    # Python multi-stage build
│   │   ├── Dockerfile.frontend   # Node + Nginx build
│   │   └── prometheus.yml        # Monitoring config
│   ├── nginx/
│   │   └── nginx.conf            # Reverse proxy config
│   ├── kubernetes/
│   │   └── k8s-deployment.yml    # K8s manifests + HPA
│   └── terraform/
│       └── main.tf               # AWS infrastructure as code
└── scripts/
    ├── setup/
    │   ├── setup.sh              # One-click installation
    │   └── migrate_and_seed.py   # DB init + demo data
    ├── deployment/
    │   └── start.sh              # Start all services
    └── maintenance/
        └── maintenance.py        # Cleanup & health checks
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### 2. Install

```bash
git clone https://github.com/quantsingularity/QuantumFence
cd QuantumFence
bash scripts/setup/setup.sh --dev
```

### 3. Configure API Keys

Edit `code/backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_MAPS_API_KEY=your-google-maps-key
```

### 4. Seed Demo Data

```bash
cd code/backend && source venv/bin/activate
python ../../scripts/setup/migrate_and_seed.py
```

### 5. Start

```bash
bash scripts/deployment/start.sh
```

Access:

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **Login**: `admin` / `quantumfence`

---

## Docker Deployment

```bash
cd infrastructure/docker
cp .env.example .env   # Edit with your API keys
docker-compose up -d
```

---

## Features

### Camera Management

- Add unlimited IP/RTSP/USB/HTTP-MJPEG cameras
- Per-camera detection configuration
- PTZ control support
- Night vision tagging
- Live status dashboard with WebSocket updates

### AI Detection (YOLOv8)

- **Person detection** near fence perimeter
- **Vehicle detection** (cars, trucks, motorcycles, buses)
- **Drone/UAV detection** with trajectory tracking
- Multi-object tracking with approach vector analysis
- Swarm detection (multiple drones coordinating)
- Confidence-based alert filtering

### Claude AI Threat Analysis

- Natural language threat summaries for operators
- Risk scoring (0.0–1.0) per detection
- Recommended immediate actions
- Drone purpose classification (surveillance/recreational/hostile)
- Multi-threat coordination detection

### Geospatial Intelligence

- Google Maps / OpenStreetMap satellite view
- KML export for Google Earth Pro
- Draw and manage geofence polygons
- Camera FOV visualization on map
- Threat heatmap overlay
- Real-world location estimation from bounding box

### Drone Watch

- Animated radar display
- Live trajectory analysis
- Altitude & speed estimation
- Authorized vs. unauthorized classification
- Loitering detection

### Analytics

- Detection timeline charts
- Alert distribution by type
- Camera performance metrics
- 24h / 7d / 30d trend analysis

### Notifications

- HTML email alerts with snapshot attachments
- Webhook integration (Slack, Teams, custom)
- Severity-based escalation
- Alert cooldown management

### Security

- JWT authentication with refresh tokens
- Role-based access (Admin / Operator / Viewer)
- All actions logged to DB

---

## API Reference

Full Swagger docs at: `http://localhost:8000/api/docs`

| Method | Endpoint                       | Description              |
| ------ | ------------------------------ | ------------------------ |
| POST   | `/api/auth/login`              | Authenticate and get JWT |
| GET    | `/api/cameras`                 | List all cameras         |
| POST   | `/api/cameras`                 | Add new camera           |
| GET    | `/api/alerts`                  | List alerts with filters |
| POST   | `/api/alerts/{id}/acknowledge` | Acknowledge alert        |
| GET    | `/api/drones`                  | Drone detection log      |
| GET    | `/api/analytics/overview`      | System overview stats    |
| GET    | `/api/geofences`               | List geofence zones      |
| WS     | `/ws/{client_id}`              | Real-time event stream   |

---

## Configuration

Key settings in `code/backend/.env`:

| Variable                     | Description                      | Default            |
| ---------------------------- | -------------------------------- | ------------------ |
| `ANTHROPIC_API_KEY`          | Claude AI API key                | —                  |
| `GOOGLE_MAPS_API_KEY`        | Maps/satellite imagery           | —                  |
| `DETECTION_CONFIDENCE`       | YOLOv8 minimum confidence        | `0.5`              |
| `AI_CONFIDENCE_THRESHOLD`    | Threshold to trigger AI analysis | `0.65`             |
| `FRAME_SKIP`                 | Process every N-th frame         | `3`                |
| `MAX_CAMERAS`                | Maximum concurrent cameras       | `64`               |
| `DEFAULT_MAP_CENTER_LAT/LNG` | Default map center coordinates   | `33.6844, 73.0479` |

---

## WebSocket Events

Connect to `ws://localhost:8000/ws/{client_id}` for live events:

```json
{ "type": "alert",           "data": { ... } }
{ "type": "detection",       "data": { "camera_id": 1, "detections": [...] } }
{ "type": "drone_detection", "data": { "camera_id": 1, "threat_level": "high" } }
{ "type": "camera_status",   "camera_id": "1", "status": "online" }
```

---

## Production Deployment

### Docker Compose (Recommended)

Includes: FastAPI backend, React frontend (Nginx), PostgreSQL, Redis, Prometheus, Grafana

### Kubernetes

```bash
kubectl apply -f infrastructure/kubernetes/k8s-deployment.yml
```

### AWS (Terraform)

```bash
cd infrastructure/terraform
terraform init && terraform plan && terraform apply
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
