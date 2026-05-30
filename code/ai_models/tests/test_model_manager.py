"""
Tests for ModelManager (ai_models/model_manager.py).
All tests use the MockYOLOModel so no GPU/weights are required.
Covers detection pipelines, result parsing, class filtering,
drone-specific logic, and mock model behaviour.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock

from ai_models.model_manager import ModelManager, MockYOLOModel, MockResult, MockBoxes

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def manager():
    """ModelManager pre-loaded with Mock models (no real weights needed)."""
    m = ModelManager()
    m.yolo_model  = MockYOLOModel(detection_type="person")
    m.drone_model = MockYOLOModel(detection_type="drone")
    m._models_loaded = True
    return m


@pytest.fixture
def blank_720p():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def noise_720p():
    rng = np.random.default_rng(seed=7)
    return (rng.random((720, 1280, 3)) * 255).astype(np.uint8)


# ─── MockYOLOModel ────────────────────────────────────────────────────────────

class TestMockYOLOModel:

    def test_mock_returns_list(self):
        model  = MockYOLOModel(detection_type="person")
        result = model(np.zeros((720, 1280, 3), dtype=np.uint8))
        assert isinstance(result, list)

    def test_mock_generates_detection_every_30_calls(self):
        model = MockYOLOModel(detection_type="drone")
        detections_found = 0
        for _ in range(30):
            results = model(np.zeros((100, 100, 3), dtype=np.uint8))
            for r in results:
                if r.boxes is not None:
                    detections_found += 1
        assert detections_found >= 1

    def test_mock_no_detection_type_returns_none_boxes(self):
        from ai_models.model_manager import MockEmptyResult
        model   = MockYOLOModel(detection_type=None)
        results = model(np.zeros((100, 100, 3), dtype=np.uint8))
        # With no type returns MockEmptyResult which has boxes=None
        for r in results:
            assert r.boxes is None

    def test_mock_boxes_has_required_attrs(self):
        boxes = MockBoxes((720, 1280, 3), "drone")
        assert hasattr(boxes, "xyxy")
        assert hasattr(boxes, "conf")
        assert hasattr(boxes, "cls")
        assert len(boxes) == 1


# ─── _parse_yolo_results ─────────────────────────────────────────────────────

class TestParseYoloResults:

    def test_parse_empty_results(self, manager):
        mock_result = MagicMock()
        mock_result.boxes = None
        dets = manager._parse_yolo_results([mock_result], "person")
        assert dets == []

    def test_parse_single_detection(self, manager):
        box        = MagicMock()
        box.xyxy   = [np.array([100.0, 200.0, 300.0, 400.0])]
        box.conf   = [np.array(0.85)]
        box.cls    = [np.array(0)]

        mock_result        = MagicMock()
        mock_result.boxes  = box

        # Patch __len__ for the loop
        type(box).__len__ = lambda self: 1

        dets = manager._parse_yolo_results([mock_result], "person")
        assert len(dets) == 1
        d = dets[0]
        assert d["confidence"]  == pytest.approx(0.85)
        assert d["class"]       == "person"
        assert len(d["bbox"])   == 4   # [x1, y1, w, h]
        # width should be x2 - x1 = 200
        assert d["bbox"][2]     == pytest.approx(200.0)

    def test_parse_vehicle_class_id(self, manager):
        """Class ID 2 → 'car'."""
        box       = MagicMock()
        box.xyxy  = [np.array([50.0, 60.0, 250.0, 260.0])]
        box.conf  = [np.array(0.78)]
        box.cls   = [np.array(2)]
        type(box).__len__ = lambda self: 1

        mock_result       = MagicMock()
        mock_result.boxes = box

        dets = manager._parse_yolo_results([mock_result], "vehicle")
        assert dets[0]["class"] == "car"

    def test_parse_multiple_detections(self, manager):
        box = MagicMock()
        box.xyxy = [
            np.array([10.0, 20.0, 110.0, 120.0]),
            np.array([300.0, 400.0, 500.0, 600.0]),
        ]
        box.conf = [np.array(0.91), np.array(0.76)]
        box.cls  = [np.array(0),    np.array(0)]
        type(box).__len__ = lambda self: 2

        mock_result       = MagicMock()
        mock_result.boxes = box

        dets = manager._parse_yolo_results([mock_result], "person")
        assert len(dets) == 2
        confs = [d["confidence"] for d in dets]
        assert any(abs(c - 0.91) < 1e-3 for c in confs)

    def test_bbox_values_rounded(self, manager):
        box       = MagicMock()
        box.xyxy  = [np.array([10.123456, 20.987654, 110.555, 120.444])]
        box.conf  = [np.array(0.88)]
        box.cls   = [np.array(0)]
        type(box).__len__ = lambda self: 1

        mock_result       = MagicMock()
        mock_result.boxes = box

        dets = manager._parse_yolo_results([mock_result], "person")
        for v in dets[0]["bbox"]:
            assert len(str(v).split(".")[-1]) <= 2, f"Not rounded to 2dp: {v}"

    def test_parse_handles_attribute_error_gracefully(self, manager):
        bad_result = MagicMock()
        bad_result.boxes = MagicMock()
        bad_result.boxes.xyxy = None   # will raise AttributeError in loop
        dets = manager._parse_yolo_results([bad_result], "person")
        assert dets == []


# ─── detect_persons ───────────────────────────────────────────────────────────

class TestDetectPersons:

    def test_returns_list(self, manager, blank_720p):
        result = manager.detect_persons(blank_720p)
        assert isinstance(result, list)

    def test_none_model_returns_empty(self, blank_720p):
        m = ModelManager()
        m.yolo_model = None
        assert hasattr(m, "detect_persons")  # verify method exists
        result = m.detect_persons(blank_720p)
        assert result == []

    def test_each_result_has_required_keys(self, manager, blank_720p):
        # Drive the mock to produce a detection
        manager.yolo_model._call_count = 29  # next call → detection
        result = manager.detect_persons(blank_720p)
        if result:
            for key in ["confidence", "bbox", "class"]:
                assert key in result[0]

    def test_confidence_in_valid_range(self, manager, blank_720p):
        manager.yolo_model._call_count = 29
        result = manager.detect_persons(blank_720p)
        for d in result:
            assert 0.0 <= d["confidence"] <= 1.0

    def test_exception_returns_empty_list(self, manager, blank_720p):
        manager.yolo_model = MagicMock(side_effect=RuntimeError("GPU OOM"))
        result = manager.detect_persons(blank_720p)
        assert result == []


# ─── detect_vehicles ──────────────────────────────────────────────────────────

class TestDetectVehicles:

    def test_returns_list(self, manager, blank_720p):
        result = manager.detect_vehicles(blank_720p)
        assert isinstance(result, list)

    def test_none_model_returns_empty(self, blank_720p):
        m = ModelManager()
        m.yolo_model = None
        assert m.detect_vehicles(blank_720p) == []

    def test_exception_returns_empty_list(self, manager, blank_720p):
        manager.yolo_model = MagicMock(side_effect=RuntimeError("err"))
        assert manager.detect_vehicles(blank_720p) == []


# ─── detect_drones ────────────────────────────────────────────────────────────

class TestDetectDrones:

    def test_returns_list(self, manager, blank_720p):
        result = manager.detect_drones(blank_720p)
        assert isinstance(result, list)

    def test_none_model_returns_empty(self, blank_720p):
        m = ModelManager()
        m.drone_model = None
        assert m.detect_drones(blank_720p) == []

    def test_drone_detections_filtered_by_size_and_position(self, manager):
        """
        Detections with a relative size > 15% of the frame or in the
        bottom 30% of the frame are NOT drones — they should be filtered out.
        """
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        large_box_result = MagicMock()
        box = MagicMock()
        # Large box: 800×800 in a 1920×1080 frame → 31% of frame → filtered
        box.xyxy  = [np.array([100.0, 100.0, 900.0, 900.0])]
        box.conf  = [np.array(0.92)]
        box.cls   = [np.array(0)]
        type(box).__len__ = lambda self: 1
        large_box_result.boxes = box

        manager.drone_model = MagicMock(return_value=[large_box_result])
        result = manager.detect_drones(frame)
        assert result == []   # filtered out by size rule

    def test_small_high_drone_passes_filter(self, manager):
        """Small bbox in upper frame quadrant passes the drone filter."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        small_box_result = MagicMock()
        box = MagicMock()
        # 40×40 px at y=100 in a 1920×1080 → tiny + in upper area
        box.xyxy  = [np.array([900.0, 100.0, 940.0, 140.0])]
        box.conf  = [np.array(0.88)]
        box.cls   = [np.array(0)]
        type(box).__len__ = lambda self: 1
        small_box_result.boxes = box

        manager.drone_model = MagicMock(return_value=[small_box_result])
        result = manager.detect_drones(frame)
        assert len(result) == 1
        assert "drone_type"  in result[0]
        assert "altitude_m"  in result[0]

    def test_exception_returns_empty(self, manager, blank_720p):
        manager.drone_model = MagicMock(side_effect=RuntimeError("err"))
        assert manager.detect_drones(blank_720p) == []


# ─── Drone classification helpers ────────────────────────────────────────────

class TestDroneClassificationHelpers:

    def test_classify_wide_aspect_ratio_is_fixed_wing(self, manager):
        drone_type = manager._classify_drone_type(w=200, h=60, relative_size=0.02)
        assert drone_type == "fixed_wing"

    def test_classify_moderate_aspect_ratio_is_quadcopter(self, manager):
        drone_type = manager._classify_drone_type(w=60, h=50, relative_size=0.02)
        assert drone_type == "quadcopter"

    def test_classify_tiny_drone_is_micro(self, manager):
        drone_type = manager._classify_drone_type(w=10, h=10, relative_size=0.0005)
        assert drone_type == "micro_drone"

    def test_altitude_estimate_small_size_is_high(self, manager):
        alt = manager._estimate_altitude(relative_size=0.0005)
        assert alt == pytest.approx(200.0)

    def test_altitude_estimate_medium_size(self, manager):
        alt = manager._estimate_altitude(relative_size=0.005)
        assert alt == pytest.approx(100.0)

    def test_altitude_estimate_large_size_is_low(self, manager):
        alt = manager._estimate_altitude(relative_size=0.08)
        assert alt == pytest.approx(20.0)


# ─── Async load_all_models ────────────────────────────────────────────────────

class TestLoadAllModels:

    @pytest.mark.asyncio
    async def test_load_all_models_sets_flag(self):
        manager = ModelManager()
        with patch("ai_models.model_manager.ModelManager._load_yolo_model",
                   new_callable=AsyncMock) as mock_yolo, \
             patch("ai_models.model_manager.ModelManager._load_drone_model",
                   new_callable=AsyncMock) as mock_drone:
            await manager.load_all_models()
            assert manager._models_loaded is True
            mock_yolo.assert_called_once()
            mock_drone.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_yolo_falls_back_to_mock_when_no_weights(self):
        manager = ModelManager()
        # ultralytics not available in test environment → falls back to MockYOLOModel
        with patch("ai_models.model_manager.YOLO", side_effect=ImportError,
                   create=True):
            await manager._load_yolo_model()
            assert isinstance(manager.yolo_model, MockYOLOModel)

    def test_models_loaded_flag_initially_false(self):
        m = ModelManager()
        assert m.models_loaded is False
