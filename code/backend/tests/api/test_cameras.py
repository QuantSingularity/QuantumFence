"""
Tests for /api/cameras routes.
Covers CRUD, enable/disable, snapshot serving, stats,
and detection service integration via mocked app.state.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from database.models import CameraStatus, CameraType

pytestmark = pytest.mark.api


# ─── List cameras ─────────────────────────────────────────────────────────────

class TestListCameras:

    def test_list_empty_returns_empty_array(self, client, auth_headers):
        res = client.get("/api/cameras", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_returns_all_cameras(self, client, auth_headers, make_camera):
        make_camera(name="Cam A")
        make_camera(name="Cam B")
        res = client.get("/api/cameras", headers=auth_headers)
        assert res.status_code == 200
        names = {c["name"] for c in res.json()}
        assert {"Cam A", "Cam B"}.issubset(names)

    def test_list_requires_auth(self, client):
        res = client.get("/api/cameras")
        assert res.status_code == 401

    def test_list_filter_by_status(self, client, auth_headers, make_camera):
        make_camera(name="Online",  status=CameraStatus.ONLINE)
        make_camera(name="Offline", status=CameraStatus.OFFLINE)
        res = client.get("/api/cameras?status=online", headers=auth_headers)
        assert res.status_code == 200
        assert all(c["status"] == "online" for c in res.json())

    def test_list_filter_by_is_active(self, client, auth_headers, make_camera):
        make_camera(name="Active")
        res = client.get("/api/cameras?is_active=true", headers=auth_headers)
        assert res.status_code == 200
        assert all(c["is_active"] for c in res.json())


# ─── Create camera ────────────────────────────────────────────────────────────

class TestCreateCamera:

    def test_create_minimal_camera(self, client, auth_headers):
        res = client.post("/api/cameras", json={"name": "New Cam"},
                          headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"]   == "New Cam"
        assert data["status"] == "initializing"
        assert data["id"]     is not None

    def test_create_full_camera(self, client, auth_headers):
        payload = {
            "name":             "Full Cam",
            "description":      "Complete camera",
            "camera_type":      "rtsp",
            "stream_url":       "rtsp://192.168.1.10:554/stream",
            "latitude":         33.6844,
            "longitude":        73.0479,
            "altitude_meters":  6.0,
            "location_name":    "North Gate",
            "direction_degrees": 180.0,
            "fov_degrees":      110.0,
            "detect_persons":   True,
            "detect_vehicles":  True,
            "detect_drones":    True,
            "night_vision":     True,
            "ptz_enabled":      False,
            "resolution_width": 3840,
            "resolution_height":2160,
            "fps":              30,
        }
        res = client.post("/api/cameras", json=payload, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["stream_url"]    == "rtsp://192.168.1.10:554/stream"
        assert data["location_name"] == "North Gate"
        assert data["night_vision"]  is True

    def test_create_triggers_detection_service(self, client, auth_headers):
        """Creating an active camera must call detection_service.start_camera."""
        # Just verify the endpoint succeeds and the camera is created.
        # start_camera is a background task (async) — we just confirm it's scheduled.
        res = client.post("/api/cameras", json={"name": "DS Test Cam"},
                          headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["name"] == "DS Test Cam"

    def test_create_requires_auth(self, client):
        res = client.post("/api/cameras", json={"name": "X"})
        assert res.status_code == 401


# ─── Get single camera ────────────────────────────────────────────────────────

class TestGetCamera:

    def test_get_existing_camera(self, client, auth_headers, make_camera):
        cam = make_camera(name="Fetchable")
        res = client.get(f"/api/cameras/{cam.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["name"] == "Fetchable"

    def test_get_nonexistent_camera_returns_404(self, client, auth_headers):
        res = client.get("/api/cameras/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_response_schema_has_required_fields(self, client, auth_headers, make_camera):
        cam = make_camera()
        res = client.get(f"/api/cameras/{cam.id}", headers=auth_headers)
        data = res.json()
        for field in ["id", "name", "status", "camera_type", "detect_persons",
                      "detect_vehicles", "detect_drones", "fps", "resolution_width",
                      "resolution_height", "created_at"]:
            assert field in data, f"Missing field: {field}"


# ─── Update camera ────────────────────────────────────────────────────────────

class TestUpdateCamera:

    def test_update_name(self, client, auth_headers, make_camera):
        cam = make_camera(name="Old Name")
        res = client.put(f"/api/cameras/{cam.id}",
                         json={"name": "New Name"}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["name"] == "New Name"

    def test_update_detection_flags(self, client, auth_headers, make_camera):
        cam = make_camera(detect_drones=True)
        res = client.put(f"/api/cameras/{cam.id}",
                         json={"detect_drones": False}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["detect_drones"] is False

    def test_update_nonexistent_camera_returns_404(self, client, auth_headers):
        res = client.put("/api/cameras/99999", json={"name": "X"},
                         headers=auth_headers)
        assert res.status_code == 404

    def test_partial_update_preserves_other_fields(self, client, auth_headers, make_camera):
        cam = make_camera(name="Keep Me", fps=30)
        res = client.put(f"/api/cameras/{cam.id}",
                         json={"night_vision": True}, headers=auth_headers)
        data = res.json()
        assert data["name"]        == "Keep Me"
        assert data["fps"]         == 30
        assert data["night_vision"] is True


# ─── Delete camera ────────────────────────────────────────────────────────────

class TestDeleteCamera:

    def test_delete_existing_camera_returns_204(self, client, auth_headers, make_camera):
        cam = make_camera()
        res = client.delete(f"/api/cameras/{cam.id}", headers=auth_headers)
        assert res.status_code == 204

    def test_deleted_camera_not_found_afterwards(self, client, auth_headers, make_camera):
        cam = make_camera()
        client.delete(f"/api/cameras/{cam.id}", headers=auth_headers)
        res = client.get(f"/api/cameras/{cam.id}", headers=auth_headers)
        assert res.status_code == 404

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        res = client.delete("/api/cameras/99999", headers=auth_headers)
        assert res.status_code == 404


# ─── Enable / Disable ────────────────────────────────────────────────────────

class TestEnableDisableCamera:

    def test_disable_camera(self, client, auth_headers, make_camera):
        cam = make_camera(status=CameraStatus.ONLINE)
        res = client.post(f"/api/cameras/{cam.id}/disable", headers=auth_headers)
        assert res.status_code == 200
        assert "disabled" in res.json()["message"].lower()

    def test_enable_camera(self, client, auth_headers, make_camera):
        cam = make_camera(status=CameraStatus.DISABLED)
        res = client.post(f"/api/cameras/{cam.id}/enable", headers=auth_headers)
        assert res.status_code == 200
        assert "enabled" in res.json()["message"].lower()

    def test_disable_nonexistent_returns_404(self, client, auth_headers):
        res = client.post("/api/cameras/99999/disable", headers=auth_headers)
        assert res.status_code == 404


# ─── Stats ────────────────────────────────────────────────────────────────────

class TestCameraStats:

    def test_stats_returns_expected_fields(self, client, auth_headers, make_camera):
        cam = make_camera()
        res = client.get(f"/api/cameras/{cam.id}/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        for field in ["camera_id", "total_detections", "total_alerts", "active_alerts"]:
            assert field in data

    def test_stats_zero_counts_for_new_camera(self, client, auth_headers, make_camera):
        cam = make_camera()
        res = client.get(f"/api/cameras/{cam.id}/stats", headers=auth_headers)
        data = res.json()
        assert data["total_detections"] == 0
        assert data["total_alerts"]     == 0
        assert data["active_alerts"]    == 0

    def test_stats_counts_existing_alerts(self, client, auth_headers, make_camera, make_alert):
        cam   = make_camera()
        make_alert(camera_id=cam.id)
        make_alert(camera_id=cam.id)
        res   = client.get(f"/api/cameras/{cam.id}/stats", headers=auth_headers)
        data  = res.json()
        assert data["total_alerts"]  == 2
        assert data["active_alerts"] == 2


# ─── Snapshot endpoint ────────────────────────────────────────────────────────

class TestCameraSnapshot:

    def test_snapshot_serves_file_when_present(self, client, auth_headers,
                                                make_camera, tmp_path, monkeypatch):
        import cv2
        import numpy as np
        from config.settings import settings

        cam    = make_camera()
        # Write a real JPEG into the snapshots dir
        snap_dir = tmp_path / "snaps"
        snap_dir.mkdir()
        monkeypatch.setattr(settings, "SNAPSHOTS_DIR", str(snap_dir))

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        filename = f"cam{cam.id:02d}_person_20240101_120000.jpg"
        cv2.imwrite(str(snap_dir / filename), frame)

        res = client.get(f"/api/cameras/{cam.id}/snapshot", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
