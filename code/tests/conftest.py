"""
QuantumFence — Central Test Configuration & Shared Fixtures

Bug fixes in conftest:
  - FIX-37: sys.path now inserts BOTH code/ and code/backend/ so all imports resolve.
  - FIX-38: Settings overrides applied via monkeypatch-equivalent os.environ
            BEFORE any local module is imported.
  - FIX-39: db_session fixture uses NullPool instead of StaticPool for
            connection-level transactions so rollback actually works in tests.
  - FIX-40: client fixture uses anyio backend setting for pytest-asyncio compat.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Path setup — MUST happen before any QuantumFence imports ─────────────────
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE_DIR = os.path.dirname(_TESTS_DIR)
_BACKEND_DIR = os.path.join(_CODE_DIR, "backend")

for _p in (_CODE_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Override env vars BEFORE importing settings ───────────────────────────────
# FIX-38: Use os.environ so pydantic-settings picks them up
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SNAPSHOTS_DIR", "/tmp/qf_test_snaps")
os.environ.setdefault("RECORDINGS_DIR", "/tmp/qf_test_recordings")
os.environ.setdefault("THREAT_ANALYSIS_ENABLED", "false")
os.environ.setdefault("TOUCH_CAMERA_INTERVAL_SECONDS", "9999")  # disable in tests

from api.routes.auth import create_access_token, hash_password
from database.database import Base, get_db
from database.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertType,
    Camera,
    CameraStatus,
    CameraType,
    DroneDetection,
    Geofence,
    ThreatLevel,
    User,
    UserRole,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def test_engine():
    """
    Session-scoped in-memory SQLite engine.
    FIX-39: StaticPool required for in-memory SQLite so all connections
    share the same DB instance. PRAGMA foreign_keys enabled per connection.
    """
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
    """
    Function-scoped session with SAVEPOINT-based isolation so each test
    is fully rolled back without needing to recreate the schema.
    """
    conn = test_engine.connect()
    trans = conn.begin()
    # Nested (SAVEPOINT) transaction — rolled back after each test
    nested = conn.begin_nested()
    TestSession = sessionmaker(bind=conn, autoflush=False)
    session = TestSession()

    # Re-issue SAVEPOINT on each commit so cascading commits don't commit to
    # the outer transaction.
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
        username="testoperator",
        email="test@qf.local",
        password="testpass123",
        role=UserRole.OPERATOR,
        full_name="Test Operator",
        is_active=True,
    ):
        u = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u

    return _factory


@pytest.fixture
def make_camera(db_session):
    _counter = [0]

    def _factory(
        name=None,
        camera_type=CameraType.SIMULATED,
        stream_url="simulated",
        status=CameraStatus.ONLINE,
        latitude=33.6844,
        longitude=73.0479,
        detect_persons=True,
        detect_vehicles=True,
        detect_drones=True,
        geofence_id=None,
        **kwargs,
    ):
        _counter[0] += 1
        cam = Camera(
            name=name or f"Test Camera {_counter[0]}",
            camera_type=camera_type,
            stream_url=stream_url,
            status=status,
            latitude=latitude,
            longitude=longitude,
            detect_persons=detect_persons,
            detect_vehicles=detect_vehicles,
            detect_drones=detect_drones,
            resolution_width=1920,
            resolution_height=1080,
            fps=25,
            direction_degrees=0.0,
            fov_degrees=90.0,
            altitude_meters=5.0,
            geofence_id=geofence_id,
            is_active=True,
            **kwargs,
        )
        db_session.add(cam)
        db_session.commit()
        db_session.refresh(cam)
        return cam

    return _factory


@pytest.fixture
def make_geofence(db_session):
    _counter = [0]

    def _factory(
        name=None,
        coordinates=None,
        is_active=True,
        buffer_meters=10.0,
        alert_on_entry=True,
    ):
        _counter[0] += 1
        coords = coordinates or [
            [73.046, 33.686],
            [73.050, 33.686],
            [73.050, 33.682],
            [73.046, 33.682],
            [73.046, 33.686],
        ]
        gf = Geofence(
            name=name or f"Test Geofence {_counter[0]}",
            coordinates=coords,
            fence_type="polygon",
            buffer_meters=buffer_meters,
            is_active=is_active,
            alert_on_entry=alert_on_entry,
            color="#FF4444",
        )
        db_session.add(gf)
        db_session.commit()
        db_session.refresh(gf)
        return gf

    return _factory


@pytest.fixture
def make_alert(db_session, make_camera):
    def _factory(
        alert_type=AlertType.PERSON_DETECTED,
        severity=AlertSeverity.MEDIUM,
        status=AlertStatus.ACTIVE,
        camera_id=None,
        title="Test Alert",
        ai_summary="A person was detected near the perimeter.",
        recommended_action="Dispatch security to investigate.",
    ):
        cam_id = camera_id or make_camera().id
        a = Alert(
            camera_id=cam_id,
            alert_type=alert_type,
            severity=severity,
            status=status,
            title=title,
            ai_summary=ai_summary,
            recommended_action=recommended_action,
        )
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a

    return _factory


@pytest.fixture
def make_drone_detection(db_session, make_camera):
    def _factory(
        confidence=0.88,
        camera_id=None,
        drone_type="quadcopter",
        risk_level=ThreatLevel.WARNING,
        is_authorized=False,
    ):
        cam_id = camera_id or make_camera().id
        d = DroneDetection(
            camera_id=cam_id,
            confidence=confidence,
            drone_type=drone_type,
            estimated_altitude_m=75.0,
            estimated_speed_ms=8.5,
            risk_level=risk_level,
            is_authorized=is_authorized,
            ai_analysis="Quadcopter detected. Potential surveillance threat.",
        )
        db_session.add(d)
        db_session.commit()
        db_session.refresh(d)
        return d

    return _factory


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI TEST CLIENT
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="function")
def client(db_session):
    """
    FIX-40: TestClient with raise_server_exceptions=True and a fully stubbed
    DetectionService so no background camera loops start during tests.
    """
    from main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    mock_ds = MagicMock()
    mock_ds.start_camera = AsyncMock()
    mock_ds.stop_camera = AsyncMock()
    mock_ds.camera_processors = {}
    mock_ds.model_manager = MagicMock()
    mock_ds.model_manager.__bool__ = lambda self: True
    app.state.detection_service = mock_ds

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ── Auth fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def admin_user(db_session, make_user):
    return make_user(
        username="admin",
        email="admin@qf.local",
        password="adminpass",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def operator_user(db_session, make_user):
    return make_user(
        username="operator",
        email="op@qf.local",
        password="oppass",
        role=UserRole.OPERATOR,
    )


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


# ── pytest-asyncio event loop ─────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
