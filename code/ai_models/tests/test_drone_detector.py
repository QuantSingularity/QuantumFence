"""
Tests for DroneDetector and DroneTrack (ai_models/drone_detector.py).
Covers multi-object tracking, threat scoring, swarm detection,
trajectory analysis, and authorised-zone logic.
"""

import math
from datetime import datetime, timedelta

import numpy as np
import pytest
from ai_models.drone_detector import DroneDetector, DroneTrack

pytestmark = pytest.mark.unit


# ─── DroneTrack ───────────────────────────────────────────────────────────────


class TestDroneTrack:

    def test_empty_track_speed_is_zero(self):
        t = DroneTrack(track_id=1)
        assert t.speed == 0.0

    def test_velocity_requires_at_least_two_positions(self):
        t = DroneTrack(track_id=1)
        t.positions.append((100, 200, 50, 80))
        assert t.velocity is None

    def test_velocity_computed_correctly(self):
        t = DroneTrack(track_id=1)
        t.positions.append((100, 200, 50, 80))
        t.positions.append((110, 210, 50, 80))
        vx, vy = t.velocity
        assert vx == pytest.approx(10.0)
        assert vy == pytest.approx(10.0)

    def test_speed_is_euclidean_magnitude(self):
        t = DroneTrack(track_id=1)
        t.positions.append((0, 0, 30, 30))
        t.positions.append((3, 4, 30, 30))  # 3-4-5 triangle
        assert t.speed == pytest.approx(5.0)

    def test_trajectory_direction_east(self):
        t = DroneTrack(track_id=1)
        t.positions.append((100, 100, 30, 30))
        t.positions.append((200, 100, 30, 30))  # moving right (east)
        assert t.trajectory_direction == pytest.approx(0.0)

    def test_trajectory_direction_south(self):
        t = DroneTrack(track_id=1)
        t.positions.append((100, 100, 30, 30))
        t.positions.append((100, 200, 30, 30))  # moving down (south in pixel space)
        assert t.trajectory_direction == pytest.approx(90.0)

    def test_is_approaching_when_bbox_grows(self):
        t = DroneTrack(track_id=1)
        for size in [20, 25, 30, 40, 50]:
            t.positions.append((300, 200, size, size))
        assert t.is_approaching is True

    def test_not_approaching_when_bbox_shrinks(self):
        t = DroneTrack(track_id=1)
        for size in [50, 40, 30, 25, 20]:
            t.positions.append((300, 200, size, size))
        assert t.is_approaching is False

    def test_is_approaching_needs_five_positions(self):
        t = DroneTrack(track_id=1)
        for size in [20, 30]:
            t.positions.append((300, 200, size, size))
        assert t.is_approaching is False

    def test_to_dict_contains_required_keys(self):
        t = DroneTrack(track_id=99)
        t.positions.append((100, 200, 30, 30))
        t.confidences.append(0.88)
        d = t.to_dict()
        for key in [
            "track_id",
            "current_position",
            "trajectory",
            "speed",
            "direction",
            "is_approaching",
            "drone_type",
            "is_authorized",
            "threat_score",
            "duration_seconds",
            "avg_confidence",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_track_id_matches(self):
        t = DroneTrack(track_id=42)
        t.positions.append((0, 0, 10, 10))
        assert t.to_dict()["track_id"] == 42

    def test_avg_confidence_computed(self):
        t = DroneTrack(track_id=1)
        t.positions.append((0, 0, 10, 10))
        t.confidences.extend([0.80, 0.90, 1.00])
        assert t.to_dict()["avg_confidence"] == pytest.approx(0.90)

    def test_duration_seconds_positive(self):
        t = DroneTrack(track_id=1)
        t.first_seen = datetime.utcnow() - timedelta(seconds=5)
        t.positions.append((0, 0, 10, 10))
        d = t.to_dict()
        # Use 4.9 to avoid floating-point timing edge cases
        assert d["duration_seconds"] >= 4.9

    def test_positions_deque_max_100(self):
        t = DroneTrack(track_id=1)
        for i in range(150):
            t.positions.append((i, i, 10, 10))
        assert len(t.positions) == 100  # maxlen=100


# ─── DroneDetector — tracking ─────────────────────────────────────────────────


class TestDroneDetectorTracking:

    @pytest.fixture
    def detector(self):
        return DroneDetector(confidence_threshold=0.45)

    @pytest.fixture
    def frame_1080p(self):
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def test_empty_detections_no_tracks(self, detector, frame_1080p):
        tracks = detector.process_frame(frame_1080p, [])
        assert tracks == []

    def test_single_detection_creates_one_track(self, detector, frame_1080p):
        dets = [{"confidence": 0.90, "bbox": [800, 200, 60, 60], "class": "drone"}]
        tracks = detector.process_frame(frame_1080p, dets)
        assert len(tracks) == 1

    def test_low_confidence_detection_ignored(self, detector, frame_1080p):
        dets = [{"confidence": 0.30, "bbox": [800, 200, 60, 60], "class": "drone"}]
        tracks = detector.process_frame(frame_1080p, dets)
        assert len(tracks) == 0

    def test_multiple_spatially_separated_detections_create_separate_tracks(
        self, detector, frame_1080p
    ):
        dets = [
            {"confidence": 0.90, "bbox": [100, 100, 40, 40], "class": "drone"},
            {"confidence": 0.85, "bbox": [1600, 800, 40, 40], "class": "drone"},
        ]
        tracks = detector.process_frame(frame_1080p, dets)
        assert len(tracks) == 2

    def test_nearby_detections_merge_into_one_track(self, detector, frame_1080p):
        dets1 = [{"confidence": 0.88, "bbox": [500, 300, 40, 40], "class": "drone"}]
        dets2 = [{"confidence": 0.85, "bbox": [510, 305, 40, 40], "class": "drone"}]
        detector.process_frame(frame_1080p, dets1)
        tracks = detector.process_frame(frame_1080p, dets2)
        assert len(tracks) == 1  # same track, just updated

    def test_stale_track_removed_after_timeout(self, detector, frame_1080p):
        dets = [{"confidence": 0.90, "bbox": [600, 300, 40, 40], "class": "drone"}]
        detector.process_frame(frame_1080p, dets)
        assert len(detector.active_tracks) == 1

        # Force stale by backdating last_seen
        for track in detector.active_tracks.values():
            track.last_seen = datetime.utcnow() - timedelta(seconds=60)

        # Next frame with no detections → stale track pruned
        detector.process_frame(frame_1080p, [])
        assert len(detector.active_tracks) == 0

    def test_track_ids_increment(self, detector, frame_1080p):
        det1 = [{"confidence": 0.90, "bbox": [100, 100, 40, 40], "class": "drone"}]
        det2 = [{"confidence": 0.88, "bbox": [1600, 800, 40, 40], "class": "drone"}]
        detector.process_frame(frame_1080p, det1)
        tracks2 = detector.process_frame(frame_1080p, det1 + det2)
        ids = {t.track_id for t in tracks2}
        assert len(ids) == 2  # two distinct IDs


# ─── DroneDetector — threat scoring ──────────────────────────────────────────


class TestThreatScoring:

    @pytest.fixture
    def detector(self):
        return DroneDetector(confidence_threshold=0.45)

    def test_base_threat_score_above_zero(self, detector):
        t = DroneTrack(track_id=1)
        t.positions.append((960, 300, 30, 30))  # small, upper frame
        score = detector._calculate_threat_score(t, (1080, 1920, 3))
        assert score > 0.0

    def test_authorised_drone_lower_score(self, detector):
        t_auth = DroneTrack(track_id=1)
        t_auth.is_authorized = True
        t_unauth = DroneTrack(track_id=2)
        t_unauth.is_authorized = False
        for t in (t_auth, t_unauth):
            t.positions.append((960, 300, 30, 30))
        s_auth = detector._calculate_threat_score(t_auth, (1080, 1920, 3))
        s_unauth = detector._calculate_threat_score(t_unauth, (1080, 1920, 3))
        assert s_auth < s_unauth

    def test_approaching_drone_higher_score(self, detector):
        t_static = DroneTrack(track_id=1)
        t_approach = DroneTrack(track_id=2)
        for size in [20, 25, 30, 40, 50]:
            t_approach.positions.append((500, 200, size, size))
        for _ in range(5):
            t_static.positions.append((500, 200, 25, 25))
        s_static = detector._calculate_threat_score(t_static, (1080, 1920, 3))
        s_approach = detector._calculate_threat_score(t_approach, (1080, 1920, 3))
        assert s_approach > s_static

    def test_long_duration_increases_score(self, detector):
        t_new = DroneTrack(track_id=1)
        t_old = DroneTrack(track_id=2)
        t_old.first_seen = datetime.utcnow() - timedelta(seconds=90)
        for t in (t_new, t_old):
            t.positions.append((500, 200, 25, 25))
        s_new = detector._calculate_threat_score(t_new, (1080, 1920, 3))
        s_old = detector._calculate_threat_score(t_old, (1080, 1920, 3))
        assert s_old > s_new

    def test_threat_score_clamped_between_0_and_1(self, detector):
        t = DroneTrack(track_id=1)
        t.first_seen = datetime.utcnow() - timedelta(seconds=200)
        for size in [20, 30, 40, 50, 60]:
            t.positions.append((960, 540, size, size))
        score = detector._calculate_threat_score(t, (1080, 1920, 3))
        assert 0.0 <= score <= 1.0


# ─── DroneDetector — swarm detection ─────────────────────────────────────────


class TestSwarmDetection:

    @pytest.fixture
    def detector(self):
        return DroneDetector(confidence_threshold=0.45)

    @pytest.fixture
    def frame(self):
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    def test_no_swarm_with_fewer_than_3_drones(self, detector, frame):
        dets = [
            {"confidence": 0.90, "bbox": [200, 100, 30, 30], "class": "drone"},
            {"confidence": 0.88, "bbox": [600, 100, 30, 30], "class": "drone"},
        ]
        detector.process_frame(frame, dets)
        assert detector.detect_swarm() is False

    def test_swarm_detected_with_similar_trajectories(self, detector, frame):
        """Three drones all moving east (direction ≈ 0°) → swarm (circular var < 0.15)."""
        for i in range(3):
            track = DroneTrack(track_id=i + 1)
            # All moving right (east) — direction ≈ 0°
            for j in range(3):
                track.positions.append((100 + i * 100 + j * 20, 300 + i * 50, 25, 25))
            detector.active_tracks[i + 1] = track

        assert detector.detect_swarm() is True

    def test_no_swarm_with_divergent_trajectories(self, detector):
        """Drones flying in completely different directions → no swarm."""
        directions_deg = [0, 90, 180, 270]  # N E S W
        for i, deg in enumerate(directions_deg):
            rad = math.radians(deg)
            track = DroneTrack(track_id=i + 1)
            track.positions.append((500, 500, 25, 25))
            track.positions.append(
                (
                    500 + 50 * math.cos(rad),
                    500 + 50 * math.sin(rad),
                    25,
                    25,
                )
            )
            detector.active_tracks[i + 1] = track
        assert detector.detect_swarm() is False


# ─── DroneDetector — helpers ──────────────────────────────────────────────────


class TestDroneDetectorHelpers:

    @pytest.fixture
    def detector(self):
        return DroneDetector(confidence_threshold=0.45)

    def test_find_nearest_track_returns_closest(self, detector):
        t1 = DroneTrack(track_id=1)
        t1.positions.append((100, 100, 20, 20))
        t2 = DroneTrack(track_id=2)
        t2.positions.append((500, 500, 20, 20))
        detector.active_tracks = {1: t1, 2: t2}
        result = detector._find_nearest_track(110, 110, max_dist=200)
        assert result is t1

    def test_find_nearest_track_returns_none_if_all_too_far(self, detector):
        t1 = DroneTrack(track_id=1)
        t1.positions.append((100, 100, 20, 20))
        detector.active_tracks = {1: t1}
        result = detector._find_nearest_track(900, 900, max_dist=50)
        assert result is None

    def test_add_authorized_zone_stored(self, detector):
        detector.add_authorized_zone(lat=33.6844, lng=73.0479, radius_m=200)
        assert len(detector._authorized_zones) == 1
        zone = detector._authorized_zones[0]
        assert zone["lat"] == 33.6844
        assert zone["radius_m"] == 200

    def test_get_summary_structure(self, detector):
        summary = detector.get_summary()
        for key in [
            "active_drones",
            "high_threat_drones",
            "swarm_detected",
            "max_threat_score",
            "tracks",
        ]:
            assert key in summary

    def test_get_summary_empty(self, detector):
        summary = detector.get_summary()
        assert summary["active_drones"] == 0
        assert summary["high_threat_drones"] == 0
        assert summary["swarm_detected"] is False
        assert summary["max_threat_score"] == 0.0
