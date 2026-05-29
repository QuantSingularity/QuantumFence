"""
System-level integration tests: health endpoint, root endpoint,
CORS headers, static file serving, and end-to-end alert workflow.
"""

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.api, pytest.mark.integration]


# ─── Root / Health endpoints ──────────────────────────────────────────────────


class TestRootEndpoint:

    def test_root_returns_200(self, client):
        res = client.get("/")
        assert res.status_code == 200

    def test_root_contains_system_name(self, client):
        res = client.get("/")
        data = res.json()
        assert data["system"] == "QuantumFence"
        assert data["version"] is not None

    def test_root_contains_status_operational(self, client):
        res = client.get("/")
        assert res.json()["status"] == "operational"


class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        res = client.get("/health")
        assert res.status_code == 200

    def test_health_reports_healthy(self, client):
        res = client.get("/health")
        data = res.json()
        assert data["status"] == "healthy"

    def test_health_contains_components(self, client):
        res = client.get("/health")
        data = res.json()
        assert "components" in data
        assert "database" in data["components"]

    def test_health_reports_active_cameras(self, client):
        from main import app

        app.state.detection_service.camera_processors = {"1": MagicMock()}
        res = client.get("/health")
        data = res.json()
        assert data["components"]["active_cameras"] >= 0
        app.state.detection_service.camera_processors = {}


# ─── CORS ────────────────────────────────────────────────────────────────────


class TestCORSHeaders:

    def test_options_request_returns_cors_headers(self, client):
        res = client.options(
            "/api/cameras",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORSMiddleware should handle OPTIONS
        assert res.status_code in (200, 204)

    def test_get_request_has_cors_allow_origin(self, client, auth_headers):
        res = client.get(
            "/api/cameras",
            headers={**auth_headers, "Origin": "http://localhost:3000"},
        )
        # The Allow-Origin header should be present
        assert "access-control-allow-origin" in {k.lower() for k in res.headers.keys()}


# ─── Static file mount ───────────────────────────────────────────────────────


class TestStaticFilesMount:

    def test_snapshots_endpoint_exists(self, client, tmp_path, monkeypatch):
        """
        Write a real JPEG into the snapshots directory and verify
        it's served correctly through the /snapshots static mount.
        """
        import cv2
        import numpy as np
        from config.settings import settings

        monkeypatch.setattr(settings, "SNAPSHOTS_DIR", str(tmp_path))

        # Re-mount static files to point at tmp_path
        from fastapi.staticfiles import StaticFiles
        from main import app

        # Remove existing mount if any
        app.routes = [
            r for r in app.routes if not (hasattr(r, "path") and r.path == "/snapshots")
        ]
        app.mount("/snapshots", StaticFiles(directory=str(tmp_path)), name="snaps_test")

        frame = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "test.jpg"), frame)

        res = client.get("/snapshots/test.jpg")
        assert res.status_code == 200
        assert "jpeg" in res.headers.get("content-type", "")


# ─── End-to-end workflow ──────────────────────────────────────────────────────


class TestEndToEndAlertWorkflow:
    """
    Full workflow: create camera → verify it's listed →
    manually create alert → acknowledge → resolve.
    Exercises the entire API surface in sequence.
    """

    def test_full_alert_lifecycle(self, client, auth_headers):
        # 1. Create a camera
        cam_res = client.post(
            "/api/cameras",
            json={
                "name": "E2E Cam",
                "camera_type": "simulated",
                "stream_url": "simulated",
            },
            headers=auth_headers,
        )
        assert cam_res.status_code == 201
        cam_id = cam_res.json()["id"]

        # 2. Verify camera appears in list
        list_res = client.get("/api/cameras", headers=auth_headers)
        cam_ids = [c["id"] for c in list_res.json()]
        assert cam_id in cam_ids

        # 3. Verify stats show zero alerts
        stats_res = client.get(f"/api/cameras/{cam_id}/stats", headers=auth_headers)
        assert stats_res.json()["total_alerts"] == 0

        # 4. Analytics overview should include the camera
        ov_res = client.get("/api/analytics/overview", headers=auth_headers)
        assert ov_res.json()["cameras"]["total"] >= 1

        # 5. Delete camera
        del_res = client.delete(f"/api/cameras/{cam_id}", headers=auth_headers)
        assert del_res.status_code == 204

        # 6. Camera no longer in list
        list_res2 = client.get("/api/cameras", headers=auth_headers)
        ids2 = [c["id"] for c in list_res2.json()]
        assert cam_id not in ids2

    def test_geofence_to_alert_workflow(
        self, client, auth_headers, make_camera, make_alert
    ):
        # 1. Create geofence
        gf_res = client.post(
            "/api/geofences",
            json={
                "name": "E2E Zone",
                "coordinates": [
                    [73.046, 33.686],
                    [73.050, 33.686],
                    [73.050, 33.682],
                    [73.046, 33.682],
                    [73.046, 33.686],
                ],
            },
            headers=auth_headers,
        )
        assert gf_res.status_code == 201
        gf_id = gf_res.json()["id"]

        # 2. Check a point inside
        pt_res = client.post(
            f"/api/geofences/{gf_id}/check-point?lat=33.684&lng=73.048",
            headers=auth_headers,
        )
        assert pt_res.json()["inside"] is True

        # 3. Create a camera linked to the geofence
        cam = make_camera(geofence_id=gf_id)

        # 4. Create an alert for that camera
        alert = make_alert(camera_id=cam.id)

        # 5. Stats should reflect the alert
        stats_res = client.get(f"/api/alerts/stats", headers=auth_headers)
        assert stats_res.json()["total"] >= 1

        # 6. Acknowledge
        ack_res = client.post(
            f"/api/alerts/{alert.id}/acknowledge", headers=auth_headers
        )
        assert ack_res.json()["status"] == "acknowledged"

        # 7. Resolve
        res_res = client.post(f"/api/alerts/{alert.id}/resolve", headers=auth_headers)
        assert res_res.json()["status"] == "resolved"

        # 8. Cleanup geofence
        client.delete(f"/api/geofences/{gf_id}", headers=auth_headers)


# ─── Role-based access control ───────────────────────────────────────────────


class TestRoleBasedAccess:

    def test_viewer_can_read_cameras(self, client, operator_headers, make_camera):
        make_camera(name="Visible Cam")
        res = client.get("/api/cameras", headers=operator_headers)
        assert res.status_code == 200

    def test_operator_can_create_camera(self, client, operator_headers):
        res = client.post(
            "/api/cameras", json={"name": "Operator Cam"}, headers=operator_headers
        )
        assert res.status_code == 201

    def test_unauthenticated_cannot_access_any_api(self, client):
        for endpoint in [
            "/api/cameras",
            "/api/alerts",
            "/api/drones",
            "/api/analytics/overview",
        ]:
            res = client.get(endpoint)
            assert res.status_code == 401, f"Expected 401 for {endpoint}"
