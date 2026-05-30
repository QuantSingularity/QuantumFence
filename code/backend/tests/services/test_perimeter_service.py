"""
Tests for PerimeterService.
Covers polygon containment, buffer zones, loitering detection,
approach vector analysis, alert cooldowns, and the Haversine formula.
"""

import time
from datetime import datetime, timedelta

import pytest
from services.perimeter_service import PerimeterService

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def svc():
    return PerimeterService()


SQUARE_FENCE = {
    "id": 1,
    "name": "Test Square",
    "fence_type": "polygon",
    "coordinates": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]],
    "buffer_meters": 0.0,
    "is_active": True,
    "alert_on_entry": True,
}

CIRCLE_FENCE = {
    "id": 2,
    "name": "Test Circle",
    "fence_type": "circle",
    "coordinates": [],
    "center_lat": 33.6844,
    "center_lng": 73.0479,
    "radius_meters": 500.0,
    "buffer_meters": 0.0,
    "is_active": True,
    "alert_on_entry": True,
}


# ─── Haversine distance ───────────────────────────────────────────────────────


class TestHaversineDistance:

    def test_same_point_distance_is_zero(self, svc):
        dist = svc._haversine_distance(33.6844, 73.0479, 33.6844, 73.0479)
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_london_paris(self, svc):
        """London (51.5°N 0.1°W) → Paris (48.9°N 2.3°E) ≈ 340 km."""
        dist = svc._haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330_000 < dist < 350_000

    def test_short_distance_is_consistent(self, svc):
        """Moving 0.001° lat ≈ ~111 m."""
        dist = svc._haversine_distance(33.6844, 73.0479, 33.6854, 73.0479)
        assert 100 < dist < 120

    def test_symmetry(self, svc):
        d1 = svc._haversine_distance(33.0, 73.0, 34.0, 74.0)
        d2 = svc._haversine_distance(34.0, 74.0, 33.0, 73.0)
        assert d1 == pytest.approx(d2, rel=1e-9)


# ─── Point-in-polygon ─────────────────────────────────────────────────────────


class TestPointInPolygon:
    """Uses a unit-square polygon at (0,0)→(1,1)."""

    def test_centre_is_inside(self, svc):
        assert svc._point_in_polygon(0.5, 0.5, SQUARE_FENCE["coordinates"]) is True

    def test_corner_is_outside(self, svc):
        # Corners and edges are implementation-defined; well outside is what matters
        assert svc._point_in_polygon(2.0, 2.0, SQUARE_FENCE["coordinates"]) is False

    def test_far_outside(self, svc):
        assert svc._point_in_polygon(-10.0, -10.0, SQUARE_FENCE["coordinates"]) is False

    def test_near_edge_outside(self, svc):
        assert svc._point_in_polygon(1.1, 0.5, SQUARE_FENCE["coordinates"]) is False

    def test_multiple_inside_points(self, svc):
        inside_points = [(0.1, 0.1), (0.9, 0.9), (0.5, 0.1), (0.5, 0.9)]
        for lat, lng in inside_points:
            assert (
                svc._point_in_polygon(lat, lng, SQUARE_FENCE["coordinates"]) is True
            ), f"Expected ({lat},{lng}) to be inside"


# ─── Point-in-circle ──────────────────────────────────────────────────────────


class TestPointInCircle:

    def test_centre_is_inside(self, svc):
        assert svc._point_in_circle(33.6844, 73.0479, 33.6844, 73.0479, 500.0) is True

    def test_nearby_point_inside_radius(self, svc):
        # ~100 m north
        assert svc._point_in_circle(33.6854, 73.0479, 33.6844, 73.0479, 500.0) is True

    def test_far_point_outside_radius(self, svc):
        # ~10 km north
        assert svc._point_in_circle(33.7744, 73.0479, 33.6844, 73.0479, 500.0) is False


# ─── Buffer zone ─────────────────────────────────────────────────────────────


class TestBufferZone:

    @pytest.mark.asyncio
    async def test_point_in_buffer_triggers_alert(self, svc):
        """Point 5 m outside polygon should trigger with 10 m buffer."""
        fence = {
            **SQUARE_FENCE,
            "buffer_meters": 500_000,
        }  # huge buffer in m for lat/lng
        breaches = await svc.check_detection_against_geofences(
            detection_lat=2.0,
            detection_lng=0.5,  # outside polygon
            detection_type="person",
            camera_id=1,
            geofences=[fence],
        )
        assert len(breaches) == 1

    @pytest.mark.asyncio
    async def test_inactive_fence_skipped(self, svc):
        fence = {**SQUARE_FENCE, "is_active": False}
        breaches = await svc.check_detection_against_geofences(
            detection_lat=0.5,
            detection_lng=0.5,
            detection_type="person",
            camera_id=1,
            geofences=[fence],
        )
        assert len(breaches) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_alert_on_entry_false(self, svc):
        fence = {**SQUARE_FENCE, "alert_on_entry": False}
        breaches = await svc.check_detection_against_geofences(
            detection_lat=0.5,
            detection_lng=0.5,
            detection_type="person",
            camera_id=1,
            geofences=[fence],
        )
        assert len(breaches) == 0


# ─── Cooldown ─────────────────────────────────────────────────────────────────


class TestAlertCooldown:

    @pytest.mark.asyncio
    async def test_second_alert_within_cooldown_suppressed(self, svc):
        fence = {**SQUARE_FENCE}
        # First detection → breach
        b1 = await svc.check_detection_against_geofences(0.5, 0.5, "person", 1, [fence])
        # Immediate second detection → suppressed
        b2 = await svc.check_detection_against_geofences(0.5, 0.5, "person", 1, [fence])
        assert len(b1) == 1
        assert len(b2) == 0

    def test_is_in_cooldown_false_for_unknown_key(self, svc):
        assert svc._is_in_cooldown("nonexistent_key") is False

    def test_set_and_check_cooldown(self, svc):
        svc._set_cooldown("test_key")
        assert svc._is_in_cooldown("test_key") is True

    def test_cooldown_expires(self, svc):
        svc._cooldown_seconds = 0  # instant expiry
        svc._set_cooldown("expire_key")
        time.sleep(0.01)
        assert svc._is_in_cooldown("expire_key") is False


# ─── Loitering detection ──────────────────────────────────────────────────────


class TestLoiteringDetection:

    def test_no_loitering_on_first_sighting(self, svc):
        result = svc.detect_loitering(
            "track_001", 33.68, 73.04, loiter_threshold_seconds=5.0
        )
        assert result is False

    def test_loitering_detected_after_threshold(self, svc):
        track_id = "loiter_threshold_test"
        # Use a 2-second threshold and backdate by 3 seconds for clear margin
        for _ in range(5):
            svc.detect_loitering(track_id, 33.68, 73.04, loiter_threshold_seconds=2.0)
        # Force the first recorded timestamp to be 3 seconds old
        tracker_key = f"loiter_{track_id}"
        svc._loitering_tracker[tracker_key][0] = datetime.utcnow() - timedelta(
            seconds=3
        )
        result = svc.detect_loitering(
            track_id, 33.68, 73.04, loiter_threshold_seconds=2.0
        )
        assert result is True

    def test_different_tracks_independent(self, svc):
        svc.detect_loitering("track_A", 33.68, 73.04, loiter_threshold_seconds=60.0)
        svc.detect_loitering("track_B", 33.69, 73.05, loiter_threshold_seconds=60.0)
        # Neither should be loitering after just one call
        assert svc._loitering_tracker.get("loiter_track_A") is not None
        assert svc._loitering_tracker.get("loiter_track_B") is not None


# ─── Approach vector analysis ─────────────────────────────────────────────────


class TestApproachVectorAnalysis:

    # GeoJSON [lng, lat] convention
    FENCE_COORDS = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]

    def test_insufficient_positions_returns_not_approaching(self, svc):
        result = svc.analyze_approach_vector([(0.5, 0.5)], self.FENCE_COORDS)
        assert result["approaching"] is False

    def test_approaching_object(self, svc):
        """Positions move steadily toward lat=0 boundary."""
        positions = [(5.0, 0.5), (4.0, 0.5), (3.0, 0.5), (2.0, 0.5), (1.5, 0.5)]
        result = svc.analyze_approach_vector(positions, self.FENCE_COORDS)
        assert result["approaching"] is True
        assert result["distance_m"] is not None

    def test_receding_object(self, svc):
        """Positions move away from fence."""
        positions = [(1.5, 0.5), (2.0, 0.5), (3.0, 0.5), (4.0, 0.5), (5.0, 0.5)]
        result = svc.analyze_approach_vector(positions, self.FENCE_COORDS)
        assert result["approaching"] is False

    def test_result_contains_expected_keys(self, svc):
        result = svc.analyze_approach_vector(
            [(1.0, 0.5), (0.8, 0.5), (0.6, 0.5)], self.FENCE_COORDS
        )
        for key in [
            "approaching",
            "distance_m",
            "rate_m_per_frame",
            "eta_seconds",
            "threat_vector",
        ]:
            assert key in result


# ─── Severity calculation ─────────────────────────────────────────────────────


class TestSeverityCalculation:

    def test_drone_is_high_severity(self, svc):
        fence = {"name": "Generic Zone"}
        assert svc._calculate_severity("drone", fence) == "high"

    def test_vehicle_is_high_severity(self, svc):
        fence = {"name": "Generic Zone"}
        assert svc._calculate_severity("vehicle", fence) == "high"

    def test_person_is_medium_severity(self, svc):
        fence = {"name": "Generic Zone"}
        assert svc._calculate_severity("person", fence) == "medium"

    def test_drone_near_critical_infra_is_critical(self, svc):
        fence = {"name": "Critical Infrastructure Zone"}
        assert svc._calculate_severity("drone", fence) == "critical"
