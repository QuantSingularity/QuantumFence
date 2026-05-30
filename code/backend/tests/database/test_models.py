"""
Tests for SQLAlchemy ORM models.
Covers field defaults, constraints, relationships, and enum correctness.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from database.models import (
    User, Camera, Alert, DroneDetection, Geofence, Detection, SystemLog,
    UserRole, CameraType, CameraStatus,
    AlertType, AlertSeverity, AlertStatus, ThreatLevel,
)
from api.routes.auth import hash_password

pytestmark = pytest.mark.integration


# ─── User ────────────────────────────────────────────────────────────────────

class TestUserModel:

    def test_create_user_with_all_fields(self, db_session):
        u = User(
            username="alice",
            email="alice@example.com",
            hashed_password=hash_password("secret"),
            full_name="Alice Smith",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)

        assert u.id is not None
        assert u.username    == "alice"
        assert u.email       == "alice@example.com"
        assert u.role        == UserRole.ADMIN
        assert u.is_active   is True
        assert u.created_at  is not None

    def test_user_default_role_is_operator(self, db_session):
        u = User(
            username="bob",
            email="bob@example.com",
            hashed_password=hash_password("x"),
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        assert u.role == UserRole.OPERATOR

    def test_user_is_active_default_true(self, db_session):
        u = User(username="carol", email="carol@example.com",
                 hashed_password=hash_password("x"))
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        assert u.is_active is True

    def test_duplicate_username_raises(self, db_session):
        u1 = User(username="dup", email="dup1@example.com",
                  hashed_password=hash_password("x"))
        u2 = User(username="dup", email="dup2@example.com",
                  hashed_password=hash_password("x"))
        db_session.add(u1); db_session.commit()
        db_session.add(u2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_all_user_roles_are_valid(self):
        roles = {r.value for r in UserRole}
        assert roles == {"admin", "operator", "viewer"}


# ─── Camera ──────────────────────────────────────────────────────────────────

class TestCameraModel:

    def test_create_minimal_camera(self, db_session):
        cam = Camera(name="Minimal Cam")
        db_session.add(cam)
        db_session.commit()
        db_session.refresh(cam)

        assert cam.id is not None
        assert cam.name               == "Minimal Cam"
        assert cam.status             == CameraStatus.INITIALIZING
        assert cam.detect_persons     is True
        assert cam.detect_vehicles    is True
        assert cam.detect_drones      is True
        assert cam.resolution_width   == 1920
        assert cam.resolution_height  == 1080
        assert cam.fps                == 25
        assert cam.fov_degrees        == 90.0

    def test_camera_with_geofence_link(self, db_session, make_geofence):
        gf  = make_geofence()
        cam = Camera(name="Geo Cam", geofence_id=gf.id)
        db_session.add(cam)
        db_session.commit()
        db_session.refresh(cam)
        assert cam.geofence_id == gf.id

    def test_all_camera_types_exist(self):
        types = {t.value for t in CameraType}
        assert "rtsp" in types
        assert "ip_camera" in types
        assert "simulated" in types

    def test_camera_status_transitions(self, db_session, make_camera):
        cam = make_camera()
        for new_status in CameraStatus:
            cam.status = new_status
            db_session.commit()
            db_session.refresh(cam)
            assert cam.status == new_status


# ─── Alert ───────────────────────────────────────────────────────────────────

class TestAlertModel:

    def test_create_alert_defaults(self, db_session, make_camera):
        cam   = make_camera()
        alert = Alert(
            camera_id  = cam.id,
            alert_type = AlertType.PERSON_DETECTED,
            title      = "Person near north fence",
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)

        assert alert.id         is not None
        assert alert.status     == AlertStatus.ACTIVE
        assert alert.severity   == AlertSeverity.MEDIUM
        assert alert.created_at is not None
        assert alert.resolved_at is None

    def test_alert_severity_ordering(self):
        sevs = [AlertSeverity.LOW, AlertSeverity.MEDIUM,
                AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        assert len(sevs) == 4

    def test_all_alert_types_exist(self):
        types = {t.value for t in AlertType}
        expected = {
            "person_detected", "vehicle_detected", "drone_detected",
            "perimeter_breach", "unknown_object", "multiple_threats",
            "loitering", "fire_smoke",
        }
        assert expected.issubset(types)

    def test_alert_acknowledge_sets_timestamp(self, db_session, make_alert, make_user):
        alert = make_alert()
        user  = make_user(username="ack_user", email="ack@qf.local")
        assert alert.acknowledged_at is None

        alert.status          = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user.id
        alert.acknowledged_at = datetime.utcnow()
        db_session.commit()
        db_session.refresh(alert)

        assert alert.status          == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_at is not None

    def test_alert_resolve_sets_timestamp(self, db_session, make_alert):
        alert = make_alert()
        alert.status      = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        db_session.commit()
        db_session.refresh(alert)
        assert alert.resolved_at is not None


# ─── DroneDetection ──────────────────────────────────────────────────────────

class TestDroneDetectionModel:

    def test_create_drone_detection(self, db_session, make_camera):
        cam = make_camera()
        det = DroneDetection(
            camera_id    = cam.id,
            confidence   = 0.93,
            drone_type   = "quadcopter",
            estimated_altitude_m = 120.0,
            estimated_speed_ms   = 12.5,
            risk_level   = ThreatLevel.THREAT,
            is_authorized = False,
        )
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        assert det.id                  is not None
        assert det.confidence          == pytest.approx(0.93)
        assert det.drone_type          == "quadcopter"
        assert det.risk_level          == ThreatLevel.THREAT
        assert det.is_authorized       is False
        assert det.timestamp           is not None

    def test_all_threat_levels_valid(self):
        levels = {t.value for t in ThreatLevel}
        assert levels == {"clear", "caution", "warning", "threat", "critical"}


# ─── Geofence ────────────────────────────────────────────────────────────────

class TestGeofenceModel:

    def test_create_geofence(self, db_session):
        coords = [[73.0, 33.7], [73.1, 33.7], [73.1, 33.6], [73.0, 33.6], [73.0, 33.7]]
        gf = Geofence(
            name        = "Test Zone",
            coordinates = coords,
            fence_type  = "polygon",
            buffer_meters   = 15.0,
            alert_on_entry  = True,
            alert_on_exit   = False,
            is_active       = True,
            color           = "#FF0000",
        )
        db_session.add(gf)
        db_session.commit()
        db_session.refresh(gf)

        assert gf.id          is not None
        assert gf.name        == "Test Zone"
        assert gf.coordinates == coords
        assert gf.buffer_meters == 15.0

    def test_geofence_default_is_active(self, db_session):
        gf = Geofence(name="Active GF",
                      coordinates=[[0,0],[1,0],[1,1],[0,1],[0,0]])
        db_session.add(gf)
        db_session.commit()
        db_session.refresh(gf)
        assert gf.is_active is True


# ─── Detection ───────────────────────────────────────────────────────────────

class TestDetectionModel:

    def test_create_detection(self, db_session, make_camera):
        cam = make_camera()
        det = Detection(
            camera_id      = cam.id,
            detection_type = "person",
            confidence     = 0.87,
            bounding_box   = {"x": 100, "y": 200, "w": 80, "h": 160},
            risk_score     = 0.6,
        )
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        assert det.id              is not None
        assert det.detection_type  == "person"
        assert det.confidence      == pytest.approx(0.87)
        assert det.bounding_box["w"] == 80
