# QuantumFence — Testing Guide

## Overview

The test suite covers **backend API routes**, **AI models**, **services**, **integrations**, and **system-level workflows**. All tests run without GPU, real camera streams, or external API keys.

---

## Test Structure

```
code/tests/
├── conftest.py                          # Shared fixtures for all tests
├── backend/
│   ├── api/
│   │   ├── test_auth.py                 # JWT auth, login, registration, token refresh
│   │   ├── test_cameras.py              # Camera CRUD, enable/disable, snapshot, stats
│   │   ├── test_routes.py               # Alerts, Drones, Analytics, Geofences routes
│   │   ├── test_websocket.py            # WebSocket connection manager
│   │   └── test_system.py              # Health/root, CORS, e2e workflows, RBAC
│   ├── database/
│   │   └── test_models.py               # ORM model validation, constraints, enums
│   ├── services/
│   │   ├── test_perimeter_service.py    # Polygon/circle containment, loitering, approach
│   │   ├── test_ai_analysis_service.py  # Claude API mocking, parsing, fallbacks
│   │   ├── test_detection_service.py    # Camera lifecycle, DB writes, alert creation
│   │   └── test_notification_service.py # Email/webhook dispatch, severity filtering
│   └── test_settings_and_edge_cases.py  # Config validation, parametrized edge cases
├── ai_models/
│   ├── test_drone_detector.py           # DroneTrack, multi-object tracking, swarm
│   └── test_model_manager.py            # YOLOv8 pipeline, bbox parsing, drone filter
└── integrations/
    └── test_google_earth.py             # KML generation, FOV polygon, location estimate
```

---

## Running Tests

### Prerequisites

```bash
# From the project root — setup must have been run first
bash scripts/setup/setup.sh --dev
```

### Run all tests

```bash
bash scripts/run_tests.sh
```

### Run by category

```bash
bash scripts/run_tests.sh unit         # Pure unit tests (fast, no DB)
bash scripts/run_tests.sh api          # FastAPI route tests
bash scripts/run_tests.sh integration  # Tests that use SQLite DB
bash scripts/run_tests.sh fast         # All except slow-marked tests
bash scripts/run_tests.sh coverage     # Full suite + HTML coverage report
```

### Run with pytest directly

```bash
cd /path/to/QuantumFence
source code/backend/venv/bin/activate
pip install -r code/backend/requirements-test.txt

# All tests
pytest code/tests/

# Specific file
pytest code/tests/ai_models/test_drone_detector.py -v

# Specific class or function
pytest code/tests/backend/api/test_auth.py::TestLoginEndpoint -v
pytest code/tests/backend/api/test_auth.py::TestLoginEndpoint::test_login_valid_credentials_returns_tokens -v

# With coverage
pytest code/tests/ --cov=code/backend --cov=code/ai_models --cov-report=html

# Stop on first failure
pytest code/tests/ -x

# Show print output
pytest code/tests/ -s
```

---

## Test Architecture

### Database Isolation

Each test function gets a **rolled-back transaction**. The `db_session` fixture opens a connection, begins a transaction, and rolls it back at test teardown — so no test pollutes another.

```python
@pytest.fixture(scope="function")
def db_session(test_engine):
    connection  = test_engine.connect()
    transaction = connection.begin()
    session     = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()   # ← all changes undone
    connection.close()
```

### FastAPI TestClient

The `client` fixture overrides the `get_db` dependency with the test session and stubs the `DetectionService` so no real camera loops start during tests:

```python
@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.state.detection_service = MagicMock(...)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### Model Factories

All fixtures follow the factory pattern — call them with optional overrides:

```python
def test_alert_creation(client, auth_headers, make_camera, make_alert):
    cam   = make_camera(name="Test Cam", detect_drones=True)
    alert = make_alert(camera_id=cam.id, severity=AlertSeverity.CRITICAL)
    ...
```

### AI Model Mocking

No GPU or real model weights are needed. `MockYOLOModel` is always used in tests:

```python
@pytest.fixture
def manager():
    m = ModelManager()
    m.yolo_model  = MockYOLOModel(detection_type="person")
    m.drone_model = MockYOLOModel(detection_type="drone")
    m._models_loaded = True
    return m
```

### External Service Mocking

- **Anthropic API**: mocked via `unittest.mock.patch` — no real Claude calls
- **Email (aiosmtplib)**: patched in `test_notification_service.py`
- **Webhook HTTP calls**: `aiohttp.ClientSession` mocked
- **WebSocket**: `MagicMock` objects with `AsyncMock` for async methods

---

## Coverage Targets

| Module                | Target | What's covered                      |
| --------------------- | ------ | ----------------------------------- |
| `backend/api/routes/` | ≥ 90%  | All endpoints, error paths, auth    |
| `backend/services/`   | ≥ 85%  | All public methods, error paths     |
| `backend/database/`   | ≥ 95%  | All models, constraints             |
| `ai_models/`          | ≥ 85%  | Detection pipeline, tracking, swarm |
| `integrations/`       | ≥ 80%  | KML, FOV polygon, URL generation    |

---

## Markers

| Marker                     | Description                           |
| -------------------------- | ------------------------------------- |
| `@pytest.mark.unit`        | Pure unit test — no DB, no network    |
| `@pytest.mark.api`         | Uses `TestClient` for HTTP requests   |
| `@pytest.mark.integration` | Uses real SQLite in-memory DB         |
| `@pytest.mark.slow`        | Takes more than 1 second              |
| `@pytest.mark.asyncio`     | Async test requiring `pytest-asyncio` |

---

## Adding New Tests

### 1. New API route

```python
# code/tests/backend/api/test_my_route.py
import pytest
pytestmark = pytest.mark.api

class TestMyRoute:
    def test_success_case(self, client, auth_headers, make_camera):
        cam = make_camera(name="My Cam")
        res = client.get(f"/api/my-route/{cam.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["field"] == "expected_value"

    def test_not_found(self, client, auth_headers):
        res = client.get("/api/my-route/99999", headers=auth_headers)
        assert res.status_code == 404
```

### 2. New AI model method

```python
# code/tests/ai_models/test_my_model.py
import pytest
import numpy as np
pytestmark = pytest.mark.unit

class TestMyModel:
    def test_returns_expected_format(self):
        from ai_models.model_manager import ModelManager
        m     = ModelManager()
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = m.my_new_method(frame)
        assert isinstance(result, list)
```

### 3. New service method

```python
# code/tests/backend/services/test_my_service.py
import pytest
from services.my_service import MyService
pytestmark = pytest.mark.unit

class TestMyService:
    @pytest.fixture
    def svc(self):
        return MyService()

    def test_core_logic(self, svc):
        result = svc.my_method(input_value)
        assert result == expected
```

---

## CI Pipeline

Tests run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`):

1. **Unit tests** — fastest, run first
2. **API tests** — FastAPI TestClient
3. **Integration tests** — SQLite in-memory
4. **Coverage report** — must be ≥ 80% or CI fails
5. **Frontend lint + build** — parallel job
6. **Docker build + health check** — validates containerisation
7. **Security scan** — bandit + safety

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'database'`**  
Run `pip install -r code/backend/requirements.txt` and ensure you're in the virtualenv.

**`ImportError: No module named 'cv2'`**  
Run `pip install opencv-python-headless` or install the full requirements.

**`pytest: command not found`**  
Activate virtualenv: `source code/backend/venv/bin/activate`

**Tests fail with `IntegrityError`**  
A test left state in the DB. Check that `db_session` fixture is being used (not a raw session), and that every test gets its own rollback scope.

**Async tests not collected**  
Ensure `pytest-asyncio` is installed and tests use `@pytest.mark.asyncio`.
