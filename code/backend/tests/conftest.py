"""
QuantumFence — Backend Test Configuration & Shared Fixtures
Located at: code/backend/tests/conftest.py

Path resolution:
  - This file lives in code/backend/tests/
  - code/backend/ is its parent  → contains all backend packages
  - code/           is grandparent → contains ai_models, integrations
  Both are added to sys.path so every import resolves correctly.
"""
import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))   # code/backend/tests
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                   # code/backend
_CODE_DIR    = os.path.dirname(_BACKEND_DIR)                # code

for _p in (_BACKEND_DIR, _CODE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Override env vars BEFORE importing settings ───────────────────────────────
os.environ.setdefault("DATABASE_URL",                 "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY",                   "test-secret-key-not-for-production")
os.environ.setdefault("ANTHROPIC_API_KEY",            "")
os.environ.setdefault("GOOGLE_MAPS_API_KEY",          "")
os.environ.setdefault("DEBUG",                        "true")
os.environ.setdefault("SNAPSHOTS_DIR",                "/tmp/qf_test_snaps")
os.environ.setdefault("RECORDINGS_DIR",               "/tmp/qf_test_recordings")
os.environ.setdefault("THREAT_ANALYSIS_ENABLED",      "false")
os.environ.setdefault("TOUCH_CAMERA_INTERVAL_SECONDS","9999")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database.database import Base, get_db
from database.models import (
    User, Camera, Alert, DroneDetection, Geofence, Detection,
    UserRole, CameraType, CameraStatus,
    AlertType, AlertSeverity, AlertStatus, ThreatLevel,
)
from api.routes.auth import hash_password, create_access_token


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """SAVEPOINT-based isolation — every test fully rolled back."""
    conn    = test_engine.connect()
    trans   = conn.begin()
    nested  = conn.begin_nested()
    Session = sessionmaker(bind=conn, autoflush=False)
    session = Session()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.expire_all()
            sess.begin_nested()

    yield session

    session.close()
    nested.rollback()
    trans.rollback()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL FACTORIES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def make_user(db_session):
    def _factory(
        username  = "testoperator",
        email     = "test@qf.local",
        password  = "testpass123",
        role      = UserRole.OPERATOR,
        full_name = "Test Operator",
        is_active = True,
    ):
        u = User(
            username        = username,
            email           = email,
            hashed_password = hash_password(password),
            full_name       = full_name,
            role            = role,
            is_active       = is_active,
        )
        db_session.add(u); db_session.commit(); db_session.refresh(u)
        return u
    return _factory


@pytest.fixture
def make_camera(db_session):
    _counter = [0]
    def _factory(
        name              = None,
        camera_type       = CameraType.SIMULATED,
        stream_url        = "simulated",
        status            = CameraStatus.ONLINE,
        latitude          = 33.6844,
        longitude         = 73.0479,
        detect_persons    = True,
        detect_vehicles   = True,
        detect_drones     = True,
        geofence_id       = None,
        **kwargs,
    ):
        _counter[0] += 1
        defaults = dict(
            name              = name or f"Test Camera {_counter[0]}",
            camera_type       = camera_type,
            stream_url        = stream_url,
            status            = status,
            latitude          = latitude,
            longitude         = longitude,
            detect_persons    = detect_persons,
            detect_vehicles   = detect_vehicles,
            detect_drones     = detect_drones,
            resolution_width  = 1920,
            resolution_height = 1080,
            fps               = 25,
            direction_degrees = 0.0,
            fov_degrees       = 90.0,
            altitude_meters   = 5.0,
            geofence_id       = geofence_id,
            is_active         = True,
        )
        # kwargs override defaults (e.g. make_camera(fps=30))
        defaults.update(kwargs)
        cam = Camera(**defaults)
        db_session.add(cam); db_session.commit(); db_session.refresh(cam)
        return cam
    return _factory


@pytest.fixture
def make_geofence(db_session):
    _counter = [0]
    def _factory(
        name           = None,
        coordinates    = None,
        is_active      = True,
        buffer_meters  = 10.0,
        alert_on_entry = True,
    ):
        _counter[0] += 1
        coords = coordinates or [
            [73.046, 33.686], [73.050, 33.686],
            [73.050, 33.682], [73.046, 33.682],
            [73.046, 33.686],
        ]
        gf = Geofence(
            name           = name or f"Test Geofence {_counter[0]}",
            coordinates    = coords,
            fence_type     = "polygon",
            buffer_meters  = buffer_meters,
            is_active      = is_active,
            alert_on_entry = alert_on_entry,
            color          = "#FF4444",
        )
        db_session.add(gf); db_session.commit(); db_session.refresh(gf)
        return gf
    return _factory


@pytest.fixture
def make_alert(db_session, make_camera):
    def _factory(
        alert_type         = AlertType.PERSON_DETECTED,
        severity           = AlertSeverity.MEDIUM,
        status             = AlertStatus.ACTIVE,
        camera_id          = None,
        title              = "Test Alert",
        ai_summary         = "A person was detected near the perimeter.",
        recommended_action = "Dispatch security to investigate.",
    ):
        cam_id = camera_id or make_camera().id
        a = Alert(
            camera_id          = cam_id,
            alert_type         = alert_type,
            severity           = severity,
            status             = status,
            title              = title,
            ai_summary         = ai_summary,
            recommended_action = recommended_action,
        )
        db_session.add(a); db_session.commit(); db_session.refresh(a)
        return a
    return _factory


@pytest.fixture
def make_drone_detection(db_session, make_camera):
    def _factory(
        confidence    = 0.88,
        camera_id     = None,
        drone_type    = "quadcopter",
        risk_level    = ThreatLevel.WARNING,
        is_authorized = False,
    ):
        cam_id = camera_id or make_camera().id
        d = DroneDetection(
            camera_id            = cam_id,
            confidence           = confidence,
            drone_type           = drone_type,
            estimated_altitude_m = 75.0,
            estimated_speed_ms   = 8.5,
            risk_level           = risk_level,
            is_authorized        = is_authorized,
            ai_analysis          = "Quadcopter detected. Potential surveillance threat.",
        )
        db_session.add(d); db_session.commit(); db_session.refresh(d)
        return d
    return _factory


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI TEST CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def client(db_session):
    from main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    mock_ds = MagicMock()
    mock_ds.start_camera      = AsyncMock()
    mock_ds.stop_camera       = AsyncMock()
    mock_ds.camera_processors = {}
    mock_ds.model_manager     = MagicMock()
    mock_ds.model_manager.__bool__ = lambda self: True
    app.state.detection_service = mock_ds

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db_session, make_user):
    return make_user(username="admin", email="admin@qf.local",
                     password="adminpass", role=UserRole.ADMIN)


@pytest.fixture
def operator_user(db_session, make_user):
    return make_user(username="operator", email="op@qf.local",
                     password="oppass", role=UserRole.OPERATOR)


@pytest.fixture
def admin_token(admin_user):
    return create_access_token({"sub": admin_user.username})


@pytest.fixture
def operator_token(operator_user):
    return create_access_token({"sub": operator_user.username})


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def operator_headers(operator_token):
    return {"Authorization": f"Bearer {operator_token}"}


# ── Frame fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def blank_frame():
    import numpy as np
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def noise_frame():
    import numpy as np
    rng = np.random.default_rng(seed=42)
    return (rng.random((720, 1280, 3)) * 255).astype(np.uint8)


# ── Event loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
