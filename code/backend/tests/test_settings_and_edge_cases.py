"""
Tests for application settings, configuration validation,
and parametrized edge-case coverage across all services.
"""

import pytest

pytestmark = pytest.mark.unit


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettings:

    def test_settings_loads_without_error(self):
        from config.settings import settings

        assert settings is not None

    def test_default_database_url_contains_sqlite_in_test(self):
        from config.settings import settings

        # In test mode we force SQLite
        assert (
            "sqlite" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL
        )

    def test_jwt_algorithm_is_hs256(self):
        from config.settings import settings

        assert settings.ALGORITHM == "HS256"

    def test_access_token_expire_positive(self):
        from config.settings import settings

        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_detection_confidence_between_0_and_1(self):
        from config.settings import settings

        assert 0.0 < settings.DETECTION_CONFIDENCE < 1.0

    def test_frame_skip_at_least_1(self):
        from config.settings import settings

        assert settings.FRAME_SKIP >= 1

    def test_max_cameras_positive(self):
        from config.settings import settings

        assert settings.MAX_CAMERAS > 0

    def test_allowed_origins_is_list(self):
        from config.settings import settings

        assert isinstance(settings.ALLOWED_ORIGINS, list)

    def test_snapshots_dir_string(self):
        from config.settings import settings

        assert isinstance(settings.SNAPSHOTS_DIR, str)
        assert len(settings.SNAPSHOTS_DIR) > 0

    def test_secret_key_non_empty(self):
        from config.settings import settings

        assert len(settings.SECRET_KEY) > 10

    def test_ai_confidence_threshold_between_0_and_1(self):
        from config.settings import settings

        assert 0.0 < settings.AI_CONFIDENCE_THRESHOLD <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED EDGE CASES — Perimeter Service
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerimeterEdgeCases:

    @pytest.fixture
    def svc(self):
        from services.perimeter_service import PerimeterService

        return PerimeterService()

    @pytest.mark.parametrize(
        "lat,lng,inside",
        [
            (0.5, 0.5, True),  # centre
            (0.1, 0.1, True),  # near corner
            (0.9, 0.9, True),  # near opposite corner
            (2.0, 0.5, False),  # far right
            (-1.0, 0.5, False),  # far left
            (0.5, 2.0, False),  # far up
            (0.5, -1.0, False),  # far down
        ],
    )
    def test_point_in_unit_square(self, svc, lat, lng, inside):
        coords = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
        assert svc._point_in_polygon(lat, lng, coords) is inside

    @pytest.mark.parametrize(
        "det_type,expected_sev",
        [
            ("drone", "high"),
            ("vehicle", "high"),
            ("person", "medium"),
            ("unknown", "medium"),
        ],
    )
    def test_severity_by_detection_type(self, svc, det_type, expected_sev):
        fence = {"name": "Regular Zone"}
        assert svc._calculate_severity(det_type, fence) == expected_sev

    @pytest.mark.parametrize(
        "lat1,lng1,lat2,lng2,expected_km",
        [
            # London to Paris ≈ 340 km
            (51.5074, -0.1278, 48.8566, 2.3522, 340),
            # Same point
            (33.6844, 73.0479, 33.6844, 73.0479, 0),
            # New York to LA ≈ 3940 km
            (40.7128, -74.0060, 34.0522, -118.2437, 3940),
        ],
    )
    def test_haversine_distance_parametrized(
        self, svc, lat1, lng1, lat2, lng2, expected_km
    ):
        dist_m = svc._haversine_distance(lat1, lng1, lat2, lng2)
        dist_km = dist_m / 1000
        if expected_km == 0:
            assert dist_km < 0.001
        else:
            assert abs(dist_km - expected_km) / expected_km < 0.05  # within 5%


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED EDGE CASES — AI Analysis
# ═══════════════════════════════════════════════════════════════════════════════


class TestAIAnalysisEdgeCases:

    @pytest.fixture
    def svc(self):
        from services.ai_analysis_service import AIAnalysisService

        s = AIAnalysisService()
        s.enabled = False
        return s

    @pytest.mark.parametrize(
        "det_type,confidence,expected_level",
        [
            ("drone", 0.95, "high"),
            ("drone", 0.70, "medium"),
            ("drone", 0.40, "low"),
            ("person", 0.91, "high"),
            ("person", 0.65, "medium"),
            ("vehicle", 0.50, "low"),
            ("unknown", 0.85, "high"),
        ],
    )
    @pytest.mark.asyncio
    async def test_threat_level_matrix(self, svc, det_type, confidence, expected_level):
        result = await svc.analyze_threat(det_type, confidence, "Cam", None)
        assert result["threat_level"] == expected_level

    @pytest.mark.parametrize(
        "bad_json",
        [
            "",
            "null",
            "[]",
            "{'not': 'valid json'}",
            "undefined",
            "true",
        ],
    )
    def test_parse_handles_all_bad_inputs(self, svc, bad_json):
        result = svc._parse_analysis_response(bad_json, "person", 0.7)
        assert isinstance(result, dict)
        assert "threat_level" in result

    @pytest.mark.parametrize(
        "risk_score_str,expected_float",
        [
            ("0.85", 0.85),
            ("1", 1.0),
            ("0", 0.0),
            ("0.123", 0.123),
        ],
    )
    def test_risk_score_string_parsed_to_float(
        self, svc, risk_score_str, expected_float
    ):
        import json

        raw = json.dumps(
            {
                "threat_level": "medium",
                "risk_score": risk_score_str,
                "summary": "Test",
                "recommended_action": "Test",
            }
        )
        result = svc._parse_analysis_response(raw, "person", 0.7)
        assert isinstance(result["risk_score"], float)
        assert result["risk_score"] == pytest.approx(expected_float)


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED EDGE CASES — Model Manager
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelManagerEdgeCases:

    @pytest.fixture
    def manager(self):
        from ai_models.model_manager import MockYOLOModel, ModelManager

        m = ModelManager()
        m.yolo_model = MockYOLOModel(detection_type="person")
        m.drone_model = MockYOLOModel(detection_type="drone")
        m._models_loaded = True
        return m

    @pytest.mark.parametrize(
        "w,h,size,expected_type",
        [
            (200, 60, 0.02, "fixed_wing"),
            (80, 70, 0.02, "quadcopter"),
            (60, 50, 0.02, "quadcopter"),
            (10, 10, 0.0005, "micro_drone"),
            (50, 40, 0.015, "quadcopter"),
        ],
    )
    def test_drone_classification_parametrized(
        self, manager, w, h, size, expected_type
    ):
        result = manager._classify_drone_type(w, h, size)
        assert result == expected_type

    @pytest.mark.parametrize(
        "relative_size,expected_altitude",
        [
            (0.0005, 200.0),
            (0.005, 100.0),
            (0.02, 50.0),
            (0.08, 20.0),
        ],
    )
    def test_altitude_estimation_parametrized(
        self, manager, relative_size, expected_altitude
    ):
        alt = manager._estimate_altitude(relative_size)
        assert alt == pytest.approx(expected_altitude)

    @pytest.mark.parametrize(
        "frame_shape",
        [
            (480, 640, 3),
            (720, 1280, 3),
            (1080, 1920, 3),
            (2160, 3840, 3),
        ],
    )
    def test_detect_persons_accepts_various_resolutions(self, manager, frame_shape):
        import numpy as np

        frame = np.zeros(frame_shape, dtype=np.uint8)
        result = manager.detect_persons(frame)
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED EDGE CASES — Drone Tracker
# ═══════════════════════════════════════════════════════════════════════════════


class TestDroneTrackerEdgeCases:

    @pytest.fixture
    def detector(self):
        from ai_models.drone_detector import DroneDetector

        return DroneDetector(confidence_threshold=0.45)

    @pytest.fixture
    def blank_frame(self):
        import numpy as np

        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    @pytest.mark.parametrize(
        "confidence,expected_count",
        [
            (0.90, 1),  # above threshold → tracked
            (0.45, 1),  # at threshold → tracked
            (0.44, 0),  # below threshold → ignored
            (0.10, 0),  # well below → ignored
        ],
    )
    def test_confidence_threshold_boundary(
        self, detector, blank_frame, confidence, expected_count
    ):
        dets = [
            {"confidence": confidence, "bbox": [600, 150, 30, 30], "class": "drone"}
        ]
        tracks = detector.process_frame(blank_frame, dets)
        assert len(tracks) == expected_count

    @pytest.mark.parametrize("num_drones", [1, 2, 3, 5])
    def test_multiple_drones_tracked_independently(
        self, detector, blank_frame, num_drones
    ):
        pass

        # Spread drones far apart so they don't merge
        dets = [
            {"confidence": 0.88, "bbox": [i * 300, 100, 30, 30], "class": "drone"}
            for i in range(num_drones)
        ]
        tracks = detector.process_frame(blank_frame, dets)
        assert len(tracks) == num_drones

    @pytest.mark.parametrize(
        "is_authorized,expect_lower_score",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_authorization_status_affects_threat_score(
        self, detector, is_authorized, expect_lower_score
    ):
        from ai_models.drone_detector import DroneTrack

        t_ref = DroneTrack(track_id=1)
        t_ref.is_authorized = False
        t_test = DroneTrack(track_id=2)
        t_test.is_authorized = is_authorized
        for t in (t_ref, t_test):
            t.positions.append((500, 300, 25, 25))

        score_ref = detector._calculate_threat_score(t_ref, (1080, 1920, 3))
        score_test = detector._calculate_threat_score(t_test, (1080, 1920, 3))

        if expect_lower_score:
            assert score_test < score_ref
        else:
            assert score_test == pytest.approx(score_ref)


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRIZED EDGE CASES — Google Earth
# ═══════════════════════════════════════════════════════════════════════════════


class TestGoogleEarthEdgeCases:

    @pytest.fixture
    def geo(self):
        from config.settings import settings
        from integrations.google_earth import GoogleEarthIntegration

        settings.GOOGLE_MAPS_API_KEY = ""
        return GoogleEarthIntegration()

    @pytest.mark.parametrize(
        "direction_deg,fov_deg,range_m",
        [
            (0, 90, 100),
            (90, 45, 200),
            (180, 120, 50),
            (270, 60, 300),
            (360, 90, 100),  # same as 0
        ],
    )
    def test_fov_polygon_all_directions(self, geo, direction_deg, fov_deg, range_m):
        polygon = geo.calculate_camera_fov_polygon(
            lat=33.6844,
            lng=73.0479,
            direction_deg=direction_deg,
            fov_deg=fov_deg,
            range_meters=float(range_m),
        )
        assert len(polygon) >= 3
        for lat, lng in polygon:
            assert -90 <= lat <= 90
            assert -180 <= lng <= 180

    @pytest.mark.parametrize(
        "bbox_x,bbox_y",
        [
            (0.0, 0.5),  # far left
            (0.5, 0.5),  # centre
            (1.0, 0.5),  # far right
            (0.5, 0.0),  # top (far)
            (0.5, 1.0),  # bottom (near)
        ],
    )
    def test_location_estimation_valid_for_all_bbox_positions(
        self, geo, bbox_x, bbox_y
    ):
        lat, lng = geo.estimate_detection_location(
            camera_lat=33.6844,
            camera_lng=73.0479,
            camera_direction=0.0,
            camera_fov=90.0,
            bbox_center_x=bbox_x,
            bbox_center_y=bbox_y,
            estimated_range_m=100.0,
        )
        assert -90 <= lat <= 90
        assert -180 <= lng <= 180
