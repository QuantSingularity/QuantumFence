"""
Tests for /api/alerts, /api/drones, /api/analytics, /api/geofences routes.
"""
import pytest
from datetime import datetime, timedelta
from database.models import (
    AlertStatus, AlertSeverity, AlertType,
    DroneDetection, ThreatLevel,
)

pytestmark = pytest.mark.api


# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertStats:

    def test_stats_zeros_on_empty_db(self, client, auth_headers):
        res = client.get("/api/alerts/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"]    == 0
        assert data["active"]   == 0
        assert data["critical"] == 0

    def test_stats_counts_by_severity(self, client, auth_headers, make_alert):
        make_alert(severity=AlertSeverity.CRITICAL)
        make_alert(severity=AlertSeverity.CRITICAL)
        make_alert(severity=AlertSeverity.HIGH)
        res  = client.get("/api/alerts/stats", headers=auth_headers)
        data = res.json()
        assert data["critical"] == 2
        assert data["high"]     == 1
        assert data["total"]    == 3

    def test_stats_by_type_field_present(self, client, auth_headers):
        res = client.get("/api/alerts/stats", headers=auth_headers)
        assert "by_type" in res.json()


class TestListAlerts:

    def test_list_empty(self, client, auth_headers):
        res = client.get("/api/alerts", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_returns_alerts(self, client, auth_headers, make_alert):
        make_alert(title="Alpha"); make_alert(title="Beta")
        res = client.get("/api/alerts", headers=auth_headers)
        assert len(res.json()) == 2

    def test_filter_by_status_active(self, client, auth_headers, make_alert):
        make_alert(status=AlertStatus.ACTIVE)
        make_alert(status=AlertStatus.RESOLVED)
        res = client.get("/api/alerts?status=active", headers=auth_headers)
        assert all(a["status"] == "active" for a in res.json())

    def test_filter_by_severity_critical(self, client, auth_headers, make_alert):
        make_alert(severity=AlertSeverity.CRITICAL)
        make_alert(severity=AlertSeverity.LOW)
        res = client.get("/api/alerts?severity=critical", headers=auth_headers)
        assert all(a["severity"] == "critical" for a in res.json())

    def test_filter_by_hours(self, client, auth_headers, make_alert, db_session):
        """Alerts older than the hours window must be excluded."""
        old_alert = make_alert(title="Old")
        # Back-date it
        old_alert.created_at = datetime.utcnow() - timedelta(hours=50)
        db_session.commit()
        make_alert(title="Recent")

        res = client.get("/api/alerts?hours=24", headers=auth_headers)
        titles = [a["title"] for a in res.json()]
        assert "Recent" in titles
        assert "Old"    not in titles

    def test_list_requires_auth(self, client):
        res = client.get("/api/alerts")
        assert res.status_code == 401

    def test_response_includes_ai_fields(self, client, auth_headers, make_alert):
        make_alert(ai_summary="AI says high risk",
                   recommended_action="Send patrol")
        res  = client.get("/api/alerts", headers=auth_headers)
        data = res.json()[0]
        assert data["ai_summary"]         == "AI says high risk"
        assert data["recommended_action"] == "Send patrol"


class TestGetAlert:

    def test_get_existing(self, client, auth_headers, make_alert):
        a = make_alert(title="GetMe")
        res = client.get(f"/api/alerts/{a.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["title"] == "GetMe"

    def test_get_nonexistent_returns_404(self, client, auth_headers):
        res = client.get("/api/alerts/99999", headers=auth_headers)
        assert res.status_code == 404


class TestAcknowledgeAlert:

    def test_acknowledge_active_alert(self, client, auth_headers, make_alert):
        a   = make_alert(status=AlertStatus.ACTIVE)
        res = client.post(f"/api/alerts/{a.id}/acknowledge", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"]         == "acknowledged"
        assert data["acknowledged_at"] is not None

    def test_acknowledge_nonexistent_returns_404(self, client, auth_headers):
        res = client.post("/api/alerts/99999/acknowledge", headers=auth_headers)
        assert res.status_code == 404


class TestResolveAlert:

    def test_resolve_sets_resolved_at(self, client, auth_headers, make_alert):
        a   = make_alert(status=AlertStatus.ACTIVE)
        res = client.post(f"/api/alerts/{a.id}/resolve", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"]      == "resolved"
        assert data["resolved_at"] is not None

    def test_resolve_acknowledged_alert(self, client, auth_headers, make_alert):
        a   = make_alert(status=AlertStatus.ACKNOWLEDGED)
        res = client.post(f"/api/alerts/{a.id}/resolve", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "resolved"


class TestUpdateAlert:

    def test_update_notes(self, client, auth_headers, make_alert):
        a   = make_alert()
        res = client.put(f"/api/alerts/{a.id}",
                         json={"notes": "Confirmed false positive"},
                         headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["notes"] == "Confirmed false positive"

    def test_update_status_to_false_positive(self, client, auth_headers, make_alert):
        a   = make_alert()
        res = client.put(f"/api/alerts/{a.id}",
                         json={"status": "false_positive"},
                         headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "false_positive"


class TestDeleteAlert:

    def test_delete_alert(self, client, auth_headers, make_alert):
        a   = make_alert()
        res = client.delete(f"/api/alerts/{a.id}", headers=auth_headers)
        assert res.status_code == 204

    def test_deleted_alert_not_found(self, client, auth_headers, make_alert):
        a   = make_alert()
        client.delete(f"/api/alerts/{a.id}", headers=auth_headers)
        res = client.get(f"/api/alerts/{a.id}", headers=auth_headers)
        assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# DRONES
# ═══════════════════════════════════════════════════════════════════════════════

class TestDroneRoutes:

    def test_list_drones_empty(self, client, auth_headers):
        res = client.get("/api/drones", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_drones_returns_detections(self, client, auth_headers, make_drone_detection):
        make_drone_detection(confidence=0.91)
        res = client.get("/api/drones?hours=48", headers=auth_headers)
        assert len(res.json()) == 1
        assert res.json()[0]["confidence"] == pytest.approx(0.91)

    def test_drone_stats_fields(self, client, auth_headers, make_drone_detection):
        make_drone_detection(is_authorized=False)
        make_drone_detection(is_authorized=True)
        res  = client.get("/api/drones/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_detections"]  == 2
        assert data["authorized"]        == 1
        assert data["unauthorized"]      == 1
        assert data["threat_percentage"] == pytest.approx(50.0)

    def test_drone_stats_zero_when_empty(self, client, auth_headers):
        res  = client.get("/api/drones/stats", headers=auth_headers)
        data = res.json()
        assert data["total_detections"]  == 0
        assert data["threat_percentage"] == 0.0

    def test_active_drones_endpoint(self, client, auth_headers):
        res = client.get("/api/drones/active", headers=auth_headers)
        assert res.status_code == 200
        assert "active_drones" in res.json()
        assert "detections"    in res.json()

    def test_drone_response_has_risk_level(self, client, auth_headers, make_drone_detection):
        make_drone_detection(risk_level=ThreatLevel.THREAT)
        res  = client.get("/api/drones?hours=48", headers=auth_headers)
        data = res.json()[0]
        assert data["risk_level"] == "threat"

    def test_drones_require_auth(self, client):
        res = client.get("/api/drones")
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyticsRoutes:

    def test_overview_structure(self, client, auth_headers):
        res  = client.get("/api/analytics/overview", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "cameras"               in data
        assert "alerts_24h"            in data
        assert "critical_alerts_24h"   in data
        assert "drone_detections_24h"  in data
        assert "detections_24h"        in data
        assert "threat_level"          in data
        assert "system_health"         in data

    def test_overview_threat_level_clear_when_no_alerts(self, client, auth_headers):
        res = client.get("/api/analytics/overview", headers=auth_headers)
        assert res.json()["threat_level"] == "CLEAR"

    def test_overview_threat_level_critical_with_critical_alerts(
        self, client, auth_headers, make_alert
    ):
        make_alert(severity=AlertSeverity.CRITICAL)
        res = client.get("/api/analytics/overview", headers=auth_headers)
        assert res.json()["threat_level"] == "CRITICAL"

    def test_detections_timeline_returns_N_days(self, client, auth_headers):
        for days in [7, 14, 30]:
            res  = client.get(f"/api/analytics/detections/timeline?days={days}",
                               headers=auth_headers)
            assert res.status_code == 200
            assert len(res.json()) == days

    def test_detections_timeline_item_structure(self, client, auth_headers):
        res  = client.get("/api/analytics/detections/timeline?days=7",
                           headers=auth_headers)
        item = res.json()[0]
        assert "date"       in item
        assert "detections" in item

    def test_alerts_by_type_structure(self, client, auth_headers):
        res  = client.get("/api/analytics/alerts/by-type?days=7",
                           headers=auth_headers)
        assert res.status_code == 200
        items = res.json()
        assert isinstance(items, list)
        for item in items:
            assert "type"  in item
            assert "count" in item

    def test_camera_performance_returns_list(self, client, auth_headers, make_camera):
        make_camera(name="Perf Cam")
        res  = client.get("/api/analytics/cameras/performance",
                           headers=auth_headers)
        assert res.status_code == 200
        cams = res.json()
        assert any(c["name"] == "Perf Cam" for c in cams)

    def test_heatmap_empty_when_no_detections(self, client, auth_headers):
        res = client.get("/api/analytics/heatmap", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_analytics_require_auth(self, client):
        res = client.get("/api/analytics/overview")
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# GEOFENCES
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeofenceRoutes:

    POLYGON = [[73.046, 33.686], [73.050, 33.686],
               [73.050, 33.682], [73.046, 33.682],
               [73.046, 33.686]]

    def test_list_geofences_empty(self, client, auth_headers):
        res = client.get("/api/geofences", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_create_geofence(self, client, auth_headers):
        res = client.post("/api/geofences", json={
            "name":        "Outer Perimeter",
            "coordinates": self.POLYGON,
            "buffer_meters": 12.0,
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"]           == "Outer Perimeter"
        assert data["buffer_meters"]  == 12.0
        assert data["is_active"]      is True

    def test_get_geofence(self, client, auth_headers, make_geofence):
        gf  = make_geofence(name="Fetchable GF")
        res = client.get(f"/api/geofences/{gf.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["name"] == "Fetchable GF"

    def test_get_nonexistent_geofence_returns_404(self, client, auth_headers):
        res = client.get("/api/geofences/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_update_geofence(self, client, auth_headers, make_geofence):
        gf  = make_geofence(name="Old Name")
        res = client.put(f"/api/geofences/{gf.id}",
                         json={"name": "New Name", "buffer_meters": 20.0},
                         headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["name"]          == "New Name"
        assert data["buffer_meters"] == 20.0

    def test_delete_geofence(self, client, auth_headers, make_geofence):
        gf  = make_geofence()
        res = client.delete(f"/api/geofences/{gf.id}", headers=auth_headers)
        assert res.status_code == 204

    def test_check_point_inside_geofence(self, client, auth_headers, make_geofence):
        """
        Polygon spans lng 73.046–73.050, lat 33.682–33.686.
        The centre point should be inside.
        """
        gf  = make_geofence(coordinates=self.POLYGON)
        lat, lng = 33.684, 73.048   # inside
        res = client.post(
            f"/api/geofences/{gf.id}/check-point?lat={lat}&lng={lng}",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["inside"] is True

    def test_check_point_outside_geofence(self, client, auth_headers, make_geofence):
        gf  = make_geofence(coordinates=self.POLYGON)
        lat, lng = 33.700, 73.100   # clearly outside
        res = client.post(
            f"/api/geofences/{gf.id}/check-point?lat={lat}&lng={lng}",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json()["inside"] is False

    def test_geofences_require_auth(self, client):
        res = client.get("/api/geofences")
        assert res.status_code == 401
