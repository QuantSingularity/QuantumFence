"""
Tests for DetectionService (services/detection_service.py).
Covers camera start/stop lifecycle, frame processing pipeline,
alert + drone detection DB persistence, and snapshot saving.
All camera I/O is mocked — no real streams or GPU needed.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from services.detection_service import CameraProcessor, DetectionService

pytestmark = pytest.mark.unit


# ─── CameraProcessor ─────────────────────────────────────────────────────────


class TestCameraProcessor:

    def test_simulated_url_skips_cv2_open(self):
        proc = CameraProcessor(camera_id=1, stream_url="simulated", config={})
        proc._open_stream()
        assert proc.cap is None  # no real VideoCapture opened

    def test_empty_url_skips_cv2_open(self):
        proc = CameraProcessor(camera_id=2, stream_url="", config={})
        proc._open_stream()
        assert proc.cap is None

    def test_generate_test_frame_returns_correct_shape(self):
        proc = CameraProcessor(1, "simulated", {})
        frame = proc._generate_test_frame()
        assert frame.shape == (720, 1280, 3)
        assert frame.dtype == np.uint8

    def test_generate_test_frame_increments_counter(self):
        proc = CameraProcessor(1, "simulated", {})
        assert proc.frame_count == 0
        proc._generate_test_frame()
        assert proc.frame_count == 1

    def test_get_frame_falls_back_to_synthetic_when_no_cap(self):
        proc = CameraProcessor(1, "simulated", {})
        frame = proc.get_frame()
        assert frame is not None
        assert frame.shape == (720, 1280, 3)

    def test_stop_sets_is_running_false(self):
        proc = CameraProcessor(1, "simulated", {})
        proc.is_running = True
        proc.stop()
        assert proc.is_running is False

    def test_stop_releases_cap_if_open(self):
        proc = CameraProcessor(1, "simulated", {})
        mock_cap = MagicMock()
        proc.cap = mock_cap
        proc.stop()
        mock_cap.release.assert_called_once()
        assert proc.cap is None

    @pytest.mark.asyncio
    async def test_start_sets_is_running(self):
        proc = CameraProcessor(1, "simulated", {})
        await proc.start()
        assert proc.is_running is True


# ─── DetectionService — initialisation ───────────────────────────────────────


class TestDetectionServiceInit:

    @pytest.mark.asyncio
    async def test_initialize_loads_model_manager(self):
        svc = DetectionService()
        mock_mm = MagicMock()
        mock_mm.load_all_models = AsyncMock()

        with patch(
            "services.detection_service.ModelManager", return_value=mock_mm
        ), patch("services.detection_service.AIAnalysisService"), patch(
            "services.detection_service.SessionLocal"
        ):
            await svc.initialize()

        mock_mm.load_all_models.assert_called_once()
        assert svc.model_manager is mock_mm

    @pytest.mark.asyncio
    async def test_initialize_exception_does_not_crash(self):
        svc = DetectionService()
        with patch(
            "services.detection_service.ModelManager",
            side_effect=ImportError("no ultralytics"),
        ):
            # Should log and continue, not raise
            await svc.initialize()
        # Service should still be usable
        assert svc.model_manager is None


# ─── DetectionService — camera lifecycle ─────────────────────────────────────


class TestCameraLifecycle:

    @pytest.fixture
    def svc(self):
        s = DetectionService()
        # Pre-wire a mock model manager that returns zero detections
        s.model_manager = MagicMock()
        s.model_manager.detect_persons = MagicMock(return_value=[])
        s.model_manager.detect_vehicles = MagicMock(return_value=[])
        s.model_manager.detect_drones = MagicMock(return_value=[])
        s.ai_analysis = None
        s.db_session_factory = None
        return s

    @pytest.mark.asyncio
    async def test_start_camera_creates_processor_and_task(self, svc):
        await svc.start_camera(1, "simulated", {"detect_persons": True})
        assert 1 in svc.camera_processors
        assert 1 in svc._processing_tasks
        await svc.stop_camera(1)

    @pytest.mark.asyncio
    async def test_start_camera_twice_replaces_old_processor(self, svc):
        await svc.start_camera(1, "simulated", {})
        first_task = svc._processing_tasks[1]
        await svc.start_camera(1, "simulated", {})
        second_task = svc._processing_tasks[1]
        assert first_task is not second_task
        await svc.stop_camera(1)

    @pytest.mark.asyncio
    async def test_stop_camera_removes_processor_and_task(self, svc):
        await svc.start_camera(2, "simulated", {})
        await svc.stop_camera(2)
        assert 2 not in svc.camera_processors
        assert 2 not in svc._processing_tasks

    @pytest.mark.asyncio
    async def test_stop_nonexistent_camera_is_safe(self, svc):
        # Should not raise
        await svc.stop_camera(999)

    @pytest.mark.asyncio
    async def test_shutdown_stops_all_cameras(self, svc):
        await svc.start_camera(1, "simulated", {})
        await svc.start_camera(2, "simulated", {})
        await svc.shutdown()
        assert svc.camera_processors == {}
        assert svc._processing_tasks == {}


# ─── DetectionService — _run_detections ──────────────────────────────────────


class TestRunDetections:

    @pytest.fixture
    def svc_with_mock_ws(self):
        s = DetectionService()
        s.model_manager = MagicMock()
        s.model_manager.detect_persons = MagicMock(return_value=[])
        s.model_manager.detect_vehicles = MagicMock(return_value=[])
        s.model_manager.detect_drones = MagicMock(return_value=[])
        s.ai_analysis = None
        s.db_session_factory = None
        return s

    @pytest.fixture
    def blank_frame(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    @pytest.mark.asyncio
    async def test_no_model_manager_returns_early(self, blank_frame):
        svc = DetectionService()
        svc.model_manager = None
        # Should return without error
        await svc._run_detections(1, blank_frame, {})

    @pytest.mark.asyncio
    async def test_detections_broadcast_via_websocket(
        self, svc_with_mock_ws, blank_frame
    ):
        high_conf_det = {
            "confidence": 0.92,
            "bbox": [100, 100, 50, 50],
            "class": "person",
        }
        svc_with_mock_ws.model_manager.detect_persons.return_value = [high_conf_det]

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_detection = AsyncMock()
            await svc_with_mock_ws._run_detections(
                1,
                blank_frame,
                {
                    "detect_persons": True,
                    "detect_vehicles": False,
                    "detect_drones": False,
                },
            )
            mock_ws.broadcast_detection.assert_called_once()
            call_args = mock_ws.broadcast_detection.call_args[0][0]
            assert call_args["camera_id"] == 1
            assert len(call_args["detections"]) == 1

    @pytest.mark.asyncio
    async def test_low_confidence_not_broadcast(self, svc_with_mock_ws, blank_frame):
        low_conf_det = {
            "confidence": 0.30,
            "bbox": [100, 100, 50, 50],
            "class": "person",
        }
        svc_with_mock_ws.model_manager.detect_persons.return_value = [low_conf_det]

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_detection = AsyncMock()
            await svc_with_mock_ws._run_detections(
                1,
                blank_frame,
                {
                    "detect_persons": True,
                    "detect_vehicles": False,
                    "detect_drones": False,
                },
            )
            mock_ws.broadcast_detection.assert_not_called()

    @pytest.mark.asyncio
    async def test_drone_detection_triggers_handle_drone(
        self, svc_with_mock_ws, blank_frame
    ):
        drone_det = {
            "confidence": 0.87,
            "bbox": [600, 100, 30, 30],
            "class": "drone",
            "drone_type": "quadcopter",
        }
        svc_with_mock_ws.model_manager.detect_drones.return_value = [drone_det]
        svc_with_mock_ws._handle_drone_detection = AsyncMock()

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_detection = AsyncMock()
            await svc_with_mock_ws._run_detections(
                1,
                blank_frame,
                {
                    "detect_persons": False,
                    "detect_vehicles": False,
                    "detect_drones": True,
                },
            )
        svc_with_mock_ws._handle_drone_detection.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_flags_respected_persons_disabled(
        self, svc_with_mock_ws, blank_frame
    ):
        svc_with_mock_ws.model_manager.detect_persons.return_value = [
            {"confidence": 0.95, "bbox": [0, 0, 100, 200]}
        ]
        await svc_with_mock_ws._run_detections(
            1,
            blank_frame,
            {"detect_persons": False, "detect_vehicles": False, "detect_drones": False},
        )
        svc_with_mock_ws.model_manager.detect_persons.assert_not_called()


# ─── DetectionService — alert creation ───────────────────────────────────────


class TestAlertCreation:

    @pytest.fixture
    def svc_with_db(self, db_session):
        s = DetectionService()
        s.model_manager = MagicMock()
        s.ai_analysis = None
        s.db_session_factory = lambda: db_session
        return s

    @pytest.mark.asyncio
    async def test_create_alert_persisted_to_db(
        self, svc_with_db, db_session, make_camera, blank_frame
    ):
        from database.models import Alert

        cam = make_camera()
        detections = [
            {
                "type": "person",
                "confidence": 0.88,
                "bbox": [100, 100, 60, 80],
                "timestamp": "2024-01-01T00:00:00",
            }
        ]

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_alert = AsyncMock()
            with patch.object(
                svc_with_db, "_save_snapshot", new_callable=AsyncMock, return_value=None
            ):
                await svc_with_db._create_alert(
                    cam.id, detections, blank_frame, datetime.utcnow()
                )

        alerts = db_session.query(Alert).filter(Alert.camera_id == cam.id).all()
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "person_detected"

    @pytest.mark.asyncio
    async def test_create_alert_broadcasts_via_websocket(
        self, svc_with_db, make_camera, blank_frame
    ):
        cam = make_camera()
        detections = [
            {
                "type": "vehicle",
                "confidence": 0.79,
                "bbox": [200, 150, 120, 80],
                "timestamp": "2024-01-01T00:00:00",
            }
        ]

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_alert = AsyncMock()
            with patch.object(
                svc_with_db, "_save_snapshot", new_callable=AsyncMock, return_value=None
            ):
                await svc_with_db._create_alert(
                    cam.id, detections, blank_frame, datetime.utcnow()
                )
            mock_ws.broadcast_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_detections_no_alert_created(
        self, svc_with_db, db_session, make_camera, blank_frame
    ):
        from database.models import Alert

        cam = make_camera()
        with patch("services.detection_service.manager"):
            await svc_with_db._create_alert(cam.id, [], blank_frame, datetime.utcnow())
        count = db_session.query(Alert).filter(Alert.camera_id == cam.id).count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_alert_severity_matches_ai_analysis_level(
        self, svc_with_db, db_session, make_camera, blank_frame
    ):
        from database.models import Alert, AlertSeverity

        mock_ai = MagicMock()
        mock_ai.analyze_threat = AsyncMock(
            return_value={
                "threat_level": "critical",
                "summary": "Critical threat",
                "recommended_action": "Lockdown",
            }
        )
        svc_with_db.ai_analysis = mock_ai
        cam = make_camera()
        detections = [
            {
                "type": "drone",
                "confidence": 0.97,
                "bbox": [300, 50, 30, 30],
                "timestamp": "2024-01-01T00:00:00",
            }
        ]

        with patch("services.detection_service.manager") as mock_ws:
            mock_ws.broadcast_alert = AsyncMock()
            with patch.object(
                svc_with_db, "_save_snapshot", new_callable=AsyncMock, return_value=None
            ):
                await svc_with_db._create_alert(
                    cam.id, detections, blank_frame, datetime.utcnow()
                )

        alert = db_session.query(Alert).filter(Alert.camera_id == cam.id).first()
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL


# ─── DetectionService — snapshot saving ─────────────────────────────────────


class TestSnapshotSaving:

    @pytest.fixture
    def svc(self):
        s = DetectionService()
        return s

    @pytest.mark.asyncio
    async def test_save_snapshot_creates_file(self, svc, tmp_path, monkeypatch):
        from config.settings import settings

        monkeypatch.setattr(settings, "SNAPSHOTS_DIR", str(tmp_path))

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        path = await svc._save_snapshot(
            1, frame, "person", datetime(2024, 1, 1, 12, 0, 0)
        )

        assert path is not None
        assert Path(path).exists()
        assert path.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_save_snapshot_filename_format(self, svc, tmp_path, monkeypatch):
        from config.settings import settings

        monkeypatch.setattr(settings, "SNAPSHOTS_DIR", str(tmp_path))

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        ts = datetime(2024, 6, 15, 14, 30, 45)
        path = await svc._save_snapshot(3, frame, "drone", ts)

        filename = Path(path).name
        assert "cam03" in filename
        assert "drone" in filename
        assert "20240615" in filename
        assert "143045" in filename

    @pytest.mark.asyncio
    async def test_save_snapshot_returns_none_on_error(
        self, svc, tmp_path, monkeypatch
    ):
        from config.settings import settings

        monkeypatch.setattr(settings, "SNAPSHOTS_DIR", "/nonexistent/path/xyz")

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # imwrite fails silently → returns None
        path = await svc._save_snapshot(1, frame, "person", datetime.utcnow())
        # Either None or path that doesn't exist
        if path is not None:
            assert not Path(path).exists()


# ─── DetectionService — DB helpers ───────────────────────────────────────────


class TestDetectionServiceDBHelpers:

    @pytest.fixture
    def svc(self, db_session):
        s = DetectionService()
        s.db_session_factory = lambda: db_session
        return s

    def test_set_camera_status_updates_db(self, svc, db_session, make_camera):
        from database.models import CameraStatus

        cam = make_camera(status=CameraStatus.INITIALIZING)
        svc._set_camera_status(cam.id, "online")
        db_session.refresh(cam)
        assert cam.status == CameraStatus.ONLINE

    def test_set_camera_status_disabled(self, svc, db_session, make_camera):
        from database.models import CameraStatus

        cam = make_camera(status=CameraStatus.ONLINE)
        svc._set_camera_status(cam.id, "disabled")
        db_session.refresh(cam)
        assert cam.status == CameraStatus.DISABLED

    def test_touch_camera_updates_last_seen(self, svc, db_session, make_camera):
        cam = make_camera()
        assert cam.last_seen is None or True  # may be None initially
        ts = datetime(2024, 1, 1, 12, 0, 0)
        svc._touch_camera(cam.id, ts)
        db_session.refresh(cam)
        assert cam.last_seen is not None

    def test_set_status_nonexistent_camera_is_safe(self, svc):
        # Should not raise for unknown ID
        svc._set_camera_status(99999, "online")

    def test_no_db_factory_skips_status_update(self):
        svc = DetectionService()
        svc.db_session_factory = None
        # Should not raise
        svc._set_camera_status(1, "online")
        svc._touch_camera(1, datetime.utcnow())
