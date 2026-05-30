"""
QuantumFence - Detection Service
Orchestrates real-time video processing and AI-powered threat detection.

Bug fixes applied:
  - FIX-1: Drone alerts no longer double-created (drone excluded from _create_alert)
  - FIX-2: DB sessions use try/finally to prevent leaks
  - FIX-3: _touch_camera throttled (once per 30 s per camera) to avoid write storm
  - FIX-4: alert.title captured before db.close() to avoid detached instance access
  - FIX-5: asyncio.to_thread wraps synchronous anthropic client call
"""
import asyncio
import logging
import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

from config.settings import settings
from api.websocket import manager

# Module-level imports so tests can patch them with patch("services.detection_service.X")
from ai_models.model_manager import ModelManager
from services.ai_analysis_service import AIAnalysisService
from database.database import SessionLocal

logger = logging.getLogger("quantumfence.detection")


class CameraProcessor:
    """Captures frames from one camera stream."""

    def __init__(self, camera_id: int, stream_url: str, config: dict):
        self.camera_id   = camera_id
        self.stream_url  = stream_url
        self.config      = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running  = False
        self.frame_count = 0

    async def start(self):
        self.is_running = True
        await asyncio.to_thread(self._open_stream)

    def _open_stream(self):
        url = self.stream_url
        if url in ("simulated", "", None):
            logger.info(f"Camera {self.camera_id}: using simulated feed")
            return
        try:
            self.cap = cv2.VideoCapture(url)
            if self.cap.isOpened():
                logger.info(f"Camera {self.camera_id}: stream opened → {url}")
            else:
                logger.warning(f"Camera {self.camera_id}: could not open {url}")
                self.cap = None
        except Exception as e:
            logger.error(f"Camera {self.camera_id}: stream error — {e}")
            self.cap = None

    def get_frame(self) -> Optional[np.ndarray]:
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.frame_count += 1
                return frame
        return self._generate_test_frame()

    def _generate_test_frame(self) -> np.ndarray:
        h, w = 720, 1280
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (18, 22, 30)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        cv2.putText(frame, f"CAM {self.camera_id:02d}  —  {ts}",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 140), 2)
        cv2.putText(frame, "SIMULATED FEED", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 200), 1)
        cy = int(h * 0.55)
        cv2.line(frame, (0, cy), (w, cy), (0, 180, 0), 2)
        cv2.putText(frame, "── PERIMETER FENCE ──", (w // 2 - 130, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 0), 1)
        self.frame_count += 1
        return frame

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None


class DetectionService:
    """
    Central detection orchestrator.
    One asyncio Task per camera → pulls frames → runs AI → stores alerts → broadcasts WS.
    """

    def __init__(self):
        self.camera_processors: Dict[int, CameraProcessor] = {}
        self._processing_tasks: Dict[int, asyncio.Task]    = {}
        self.model_manager       = None
        self.ai_analysis         = None
        self.db_session_factory  = None
        # FIX-3: Throttle last_seen writes — track last write time per camera
        self._last_touch: Dict[int, datetime] = {}

    async def initialize(self):
        """Load AI models and wire up DB session factory."""
        try:
            self.model_manager      = ModelManager()
            await self.model_manager.load_all_models()
            self.ai_analysis        = AIAnalysisService()
            self.db_session_factory = SessionLocal
            logger.info("Detection service: all AI models loaded")
        except Exception as e:
            logger.error(f"Detection service init error: {e}")

    # ── Public start / stop ─────────────────────────────────────────────────

    async def start_camera(self, camera_id: int, stream_url: str, config: dict):
        if camera_id in self.camera_processors:
            await self.stop_camera(camera_id)

        proc = CameraProcessor(camera_id, stream_url, config)
        await proc.start()
        self.camera_processors[camera_id] = proc

        task = asyncio.create_task(
            self._process_loop(camera_id),
            name=f"cam_{camera_id}",
        )
        self._processing_tasks[camera_id] = task

        self._set_camera_status(camera_id, "online")
        await manager.broadcast_camera_status(str(camera_id), "online")
        logger.info(f"Camera {camera_id}: detection started")

    async def stop_camera(self, camera_id: int):
        task = self._processing_tasks.pop(camera_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        proc = self.camera_processors.pop(camera_id, None)
        if proc:
            proc.stop()

        self._last_touch.pop(camera_id, None)
        self._set_camera_status(camera_id, "disabled")
        await manager.broadcast_camera_status(str(camera_id), "disabled")
        logger.info(f"Camera {camera_id}: detection stopped")

    async def shutdown(self):
        for cam_id in list(self.camera_processors.keys()):
            await self.stop_camera(cam_id)
        logger.info("Detection service: shutdown complete")

    # ── Processing loop ─────────────────────────────────────────────────────

    async def _process_loop(self, camera_id: int):
        proc        = self.camera_processors[camera_id]
        frame_count = 0
        skip        = max(1, settings.FRAME_SKIP)

        while proc.is_running:
            try:
                frame = proc.get_frame()
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                frame_count += 1
                if frame_count % skip != 0:
                    await asyncio.sleep(0.02)
                    continue

                await self._run_detections(camera_id, frame, proc.config)
                await asyncio.sleep(1.0 / 15)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Camera {camera_id} processing error: {e}")
                await asyncio.sleep(1.0)

        logger.info(f"Camera {camera_id}: processing loop exited")

    # ── Detection pipeline ──────────────────────────────────────────────────

    async def _run_detections(self, camera_id: int, frame: np.ndarray, config: dict):
        if not self.model_manager:
            return

        person_vehicle_results: list = []
        drone_results: list          = []
        timestamp = datetime.utcnow()

        try:
            if config.get("detect_persons", True):
                for det in await asyncio.to_thread(self.model_manager.detect_persons, frame):
                    person_vehicle_results.append(
                        {**det, "type": "person", "timestamp": timestamp.isoformat()}
                    )

            if config.get("detect_vehicles", True):
                for det in await asyncio.to_thread(self.model_manager.detect_vehicles, frame):
                    person_vehicle_results.append(
                        {**det, "type": "vehicle", "timestamp": timestamp.isoformat()}
                    )

            if config.get("detect_drones", True):
                for det in await asyncio.to_thread(self.model_manager.detect_drones, frame):
                    entry = {**det, "type": "drone", "timestamp": timestamp.isoformat()}
                    drone_results.append(entry)
                    # FIX-1: Drone detection handled exclusively here — not forwarded to
                    # _create_alert so a separate Alert + DroneDetection row are NOT
                    # both created for the same event.
                    if det["confidence"] >= settings.AI_CONFIDENCE_THRESHOLD:
                        await self._handle_drone_detection(camera_id, det, frame, timestamp)

            # Person/vehicle alerts only — drones handled above
            confident_pv = [
                r for r in person_vehicle_results
                if r["confidence"] >= settings.AI_CONFIDENCE_THRESHOLD
            ]

            # Broadcast all high-confidence detections (persons + vehicles + drones)
            all_confident = confident_pv + [
                d for d in drone_results
                if d["confidence"] >= settings.AI_CONFIDENCE_THRESHOLD
            ]
            if all_confident:
                await manager.broadcast_detection({
                    "camera_id":  camera_id,
                    "detections": all_confident,
                    "timestamp":  timestamp.isoformat(),
                })

            # Create Alert rows only for persons/vehicles
            if confident_pv:
                await self._create_alert(camera_id, confident_pv, frame, timestamp)

            # FIX-3: Throttled last_seen write
            self._touch_camera_throttled(camera_id, timestamp)

        except Exception as e:
            logger.error(f"Detection pipeline error camera {camera_id}: {e}")

    # ── Drone handling ──────────────────────────────────────────────────────

    async def _handle_drone_detection(
        self, camera_id: int, det: dict,
        frame: np.ndarray, timestamp: datetime,
    ):
        snap = await self._save_snapshot(camera_id, frame, "drone", timestamp)

        if self.ai_analysis:
            # FIX-5: Wrap synchronous Anthropic client in asyncio.to_thread
            analysis = await asyncio.to_thread(
                self._sync_analyze_drone,
                det["confidence"],
                det.get("drone_type"),
                det.get("altitude_m"),
                det.get("speed_ms"),
                f"Camera {camera_id:02d}",
                snap,
            )
        else:
            analysis = {
                "threat_level": "high", "risk_score": 0.8,
                "summary": "Drone detected near perimeter.",
                "recommended_action": "Alert security and track trajectory.",
            }

        # FIX-2: Use try/finally to guarantee DB session is closed
        if self.db_session_factory:
            db = None
            try:
                from database.models import DroneDetection, ThreatLevel
                risk_map = {
                    "low": ThreatLevel.CAUTION, "medium": ThreatLevel.WARNING,
                    "high": ThreatLevel.THREAT, "critical": ThreatLevel.CRITICAL,
                }
                db = self.db_session_factory()
                row = DroneDetection(
                    camera_id            = camera_id,
                    confidence           = det["confidence"],
                    bounding_box         = {"bbox": det.get("bbox", [])},
                    snapshot_path        = snap,
                    drone_type           = det.get("drone_type", "unknown"),
                    estimated_altitude_m = det.get("altitude_m"),
                    estimated_speed_ms   = det.get("speed_ms"),
                    risk_level           = risk_map.get(
                        analysis.get("threat_level", "medium"), ThreatLevel.WARNING
                    ),
                    ai_analysis  = analysis.get("summary"),
                    is_authorized = False,
                )
                db.add(row)
                db.commit()
            except Exception as e:
                logger.error(f"DroneDetection DB error: {e}")
                if db:
                    db.rollback()
            finally:
                if db:
                    db.close()

        await manager.broadcast_drone_detection({
            "camera_id":    camera_id,
            "confidence":   det["confidence"],
            "threat_level": analysis.get("threat_level", "high"),
            "summary":      analysis.get("summary"),
            "timestamp":    timestamp.isoformat(),
        })

    def _sync_analyze_drone(self, confidence, drone_type, altitude_m,
                             speed_ms, camera_name, snapshot_path):
        """Synchronous wrapper for drone analysis (called via asyncio.to_thread)."""
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.ai_analysis.analyze_drone_threat(
                    confidence=confidence,
                    drone_type=drone_type,
                    altitude_m=altitude_m,
                    speed_ms=speed_ms,
                    camera_name=camera_name,
                    snapshot_path=snapshot_path,
                )
            )
        finally:
            loop.close()

    # ── Alert creation ──────────────────────────────────────────────────────

    async def _create_alert(
        self, camera_id: int, detections: list,
        frame: np.ndarray, timestamp: datetime,
    ):
        if not detections:
            return

        primary = max(detections, key=lambda d: d["confidence"])
        snap    = await self._save_snapshot(camera_id, frame, primary["type"], timestamp)

        if self.ai_analysis:
            analysis = await asyncio.to_thread(
                self._sync_analyze_threat,
                primary["type"], primary["confidence"],
                f"Camera {camera_id:02d}", detections, snap,
            )
        else:
            analysis = {
                "threat_level": "medium",
                "summary": f"{primary['type'].title()} detected near perimeter.",
                "recommended_action": "Review camera feed immediately.",
            }

        if not self.db_session_factory:
            return

        db = None
        try:
            from database.models import Alert, AlertType, AlertSeverity, AlertStatus

            type_map = {
                "person":  AlertType.PERSON_DETECTED,
                "vehicle": AlertType.VEHICLE_DETECTED,
                "drone":   AlertType.DRONE_DETECTED,
            }
            sev_map = {
                "low":      AlertSeverity.LOW,
                "medium":   AlertSeverity.MEDIUM,
                "high":     AlertSeverity.HIGH,
                "critical": AlertSeverity.CRITICAL,
            }

            db    = self.db_session_factory()
            title = f"{primary['type'].title()} detected — Camera {camera_id:02d}"
            alert = Alert(
                camera_id          = camera_id,
                alert_type         = type_map.get(primary["type"], AlertType.UNKNOWN_OBJECT),
                severity           = sev_map.get(
                    analysis.get("threat_level", "medium"), AlertSeverity.MEDIUM
                ),
                status             = AlertStatus.ACTIVE,
                title              = title,
                description        = analysis.get("summary"),
                ai_summary         = analysis.get("summary"),
                recommended_action = analysis.get("recommended_action"),
                snapshot_path      = snap,
                detection_data     = {"detections": detections},
            )
            db.add(alert)
            db.commit()
            # FIX-4: Capture values BEFORE closing the session
            alert_id    = alert.id
            alert_title = alert.title
        except Exception as e:
            logger.error(f"Alert DB error: {e}")
            if db:
                db.rollback()
            return
        finally:
            if db:
                db.close()

        await manager.broadcast_alert({
            "id":        alert_id,
            "camera_id": camera_id,
            "type":      primary["type"],
            "severity":  analysis.get("threat_level", "medium"),
            "title":     alert_title,
            "summary":   analysis.get("summary"),
            "timestamp": timestamp.isoformat(),
        })

    def _sync_analyze_threat(self, detection_type, confidence,
                              camera_name, detections, snap):
        """Synchronous wrapper for threat analysis (called via asyncio.to_thread)."""
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.ai_analysis.analyze_threat(
                    detection_type     = detection_type,
                    confidence         = confidence,
                    camera_name        = camera_name,
                    camera_location    = None,
                    additional_context = {"detections": detections},
                    snapshot_path      = snap,
                )
            )
        finally:
            loop.close()

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _save_snapshot(
        self, camera_id: int, frame: np.ndarray,
        label: str, timestamp: datetime,
    ) -> Optional[str]:
        try:
            Path(settings.SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
            name = f"cam{camera_id:02d}_{label}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            path = str(Path(settings.SNAPSHOTS_DIR) / name)
            await asyncio.to_thread(
                cv2.imwrite, path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85]
            )
            return path
        except Exception as e:
            logger.error(f"Snapshot save error: {e}")
            return None

    def _set_camera_status(self, camera_id: int, status: str):
        if not self.db_session_factory:
            return
        db = None
        try:
            from database.models import Camera, CameraStatus
            status_map = {
                "online":       CameraStatus.ONLINE,
                "offline":      CameraStatus.OFFLINE,
                "disabled":     CameraStatus.DISABLED,
                "initializing": CameraStatus.INITIALIZING,
                "error":        CameraStatus.ERROR,
            }
            db  = self.db_session_factory()
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if cam:
                cam.status = status_map.get(status, CameraStatus.OFFLINE)
                db.commit()
        except Exception as e:
            logger.error(f"Camera status update error: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()

    def _touch_camera_throttled(self, camera_id: int, timestamp: datetime):
        """
        FIX-3: Write last_seen at most once every TOUCH_CAMERA_INTERVAL_SECONDS
        to avoid a DB write storm on every detected frame.
        """
        interval = timedelta(seconds=settings.TOUCH_CAMERA_INTERVAL_SECONDS)
        last = self._last_touch.get(camera_id)
        if last is not None and (timestamp - last) < interval:
            return
        self._last_touch[camera_id] = timestamp
        self._touch_camera(camera_id, timestamp)

    def _touch_camera(self, camera_id: int, timestamp: datetime):
        if not self.db_session_factory:
            return
        db = None
        try:
            from database.models import Camera
            db  = self.db_session_factory()
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if cam:
                cam.last_seen = timestamp
                db.commit()
        except Exception:
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
