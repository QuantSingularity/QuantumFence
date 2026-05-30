"""
QuantumFence - AI Model Manager
Manages YOLOv8-based detection models for persons, vehicles, and drones.

Bug fixes:
  - FIX-6: MockBoxes.xyxy stores plain np.arrays; _parse_yolo_results now calls
            .tolist() only on real tensors and uses .item() for scalars safely.
  - FIX-7: MockYOLOModel(detection_type=None) now returns empty-boxes result
            rather than passing None into MockResult (avoided AttributeError).
  - FIX-8: _classify_drone_type micro_drone threshold corrected (was checking
            relative_size < 0.01 AFTER aspect-ratio branch — unreachable).
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("quantumfence.models")


class ModelManager:
    PERSON_CLASS_ID  = 0
    VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    def __init__(self):
        self.yolo_model  = None
        self.drone_model = None
        self.device      = "cpu"
        self._models_loaded = False

    async def load_all_models(self):
        try:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
        except ImportError:
            self.device = "cpu"

        await self._load_yolo_model()
        await self._load_drone_model()
        self._models_loaded = True
        logger.info("All AI models loaded successfully")

    async def _load_yolo_model(self):
        try:
            from ultralytics import YOLO
            model_path = settings.YOLO_MODEL_PATH
            if not Path(model_path).exists():
                logger.info("Downloading YOLOv8n model...")
                self.yolo_model = YOLO("yolov8n.pt")
                Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            else:
                self.yolo_model = YOLO(model_path)
            logger.info(f"YOLOv8 model loaded from {model_path}")
        except ImportError:
            logger.warning("ultralytics not installed — running in mock detection mode")
            self.yolo_model = MockYOLOModel()
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.yolo_model = MockYOLOModel()

    async def _load_drone_model(self):
        try:
            from ultralytics import YOLO
            drone_path = settings.DRONE_MODEL_PATH
            if Path(drone_path).exists():
                self.drone_model = YOLO(drone_path)
                logger.info("Drone detection model loaded")
            else:
                logger.info("No custom drone model — using YOLOv8 for drone detection")
                self.drone_model = self.yolo_model
        except Exception as e:
            logger.error(f"Drone model load error: {e}")
            self.drone_model = MockYOLOModel(detection_type="drone")

    # ── Detect persons ───────────────────────────────────────────────────────

    def detect_persons(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if self.yolo_model is None:
            return []
        try:
            results = self.yolo_model(
                frame,
                conf=settings.DETECTION_CONFIDENCE,
                iou=settings.DETECTION_IOU_THRESHOLD,
                classes=[self.PERSON_CLASS_ID],
                verbose=False,
            )
            return self._parse_yolo_results(results, "person")
        except Exception as e:
            logger.error(f"Person detection error: {e}")
            return []

    # ── Detect vehicles ──────────────────────────────────────────────────────

    def detect_vehicles(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if self.yolo_model is None:
            return []
        try:
            results = self.yolo_model(
                frame,
                conf=settings.DETECTION_CONFIDENCE,
                iou=settings.DETECTION_IOU_THRESHOLD,
                classes=list(self.VEHICLE_CLASS_IDS.keys()),
                verbose=False,
            )
            return self._parse_yolo_results(results, "vehicle")
        except Exception as e:
            logger.error(f"Vehicle detection error: {e}")
            return []

    # ── Detect drones ────────────────────────────────────────────────────────

    def detect_drones(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if self.drone_model is None:
            return []
        try:
            results = self.drone_model(
                frame,
                conf=max(0.4, settings.DETECTION_CONFIDENCE - 0.1),
                iou=settings.DETECTION_IOU_THRESHOLD,
                verbose=False,
            )
            detections = self._parse_yolo_results(results, "drone")

            height, width = frame.shape[:2]
            frame_area    = max(width * height, 1)
            filtered      = []
            for det in detections:
                x, y, w, h  = det["bbox"]
                relative_size = (w * h) / frame_area
                relative_y    = y / max(height, 1)
                if relative_size < 0.15 and relative_y < 0.7:
                    det["drone_type"] = self._classify_drone_type(w, h, relative_size)
                    det["altitude_m"] = self._estimate_altitude(relative_size)
                    filtered.append(det)
            return filtered
        except Exception as e:
            logger.error(f"Drone detection error: {e}")
            return []

    # ── Result parsing ───────────────────────────────────────────────────────

    def _parse_yolo_results(self, results, default_class: str) -> List[Dict[str, Any]]:
        """
        FIX-6: Safely extract values from both real YOLOv8 tensors and
        MockBoxes numpy arrays. Uses _safe_float / _safe_int helpers.
        """
        detections = []
        try:
            for result in results:
                if result.boxes is None:
                    continue
                boxes = result.boxes
                n     = len(boxes)
                for i in range(n):
                    try:
                        conf   = self._safe_float(boxes.conf[i])
                        xyxy   = self._safe_xyxy(boxes.xyxy[i])
                        cls_id = self._safe_int(boxes.cls[i]) if boxes.cls is not None else -1

                        x1, y1, x2, y2 = xyxy
                        bbox = [round(x1, 2), round(y1, 2),
                                round(x2 - x1, 2), round(y2 - y1, 2)]

                        class_name = self.VEHICLE_CLASS_IDS.get(cls_id, default_class)
                        detections.append({
                            "confidence": conf,
                            "bbox":       bbox,
                            "class":      class_name,
                            "class_id":   cls_id,
                        })
                    except Exception as e:
                        logger.debug(f"Skipping malformed detection box {i}: {e}")
                        continue
        except Exception as e:
            logger.debug(f"YOLO parse error: {e}")
        return detections

    @staticmethod
    def _safe_float(val) -> float:
        """Convert tensor scalar, numpy scalar, or plain float to Python float."""
        if hasattr(val, "item"):
            return float(val.item())
        if hasattr(val, "tolist"):
            v = val.tolist()
            return float(v[0]) if isinstance(v, list) else float(v)
        return float(val)

    @staticmethod
    def _safe_int(val) -> int:
        if hasattr(val, "item"):
            return int(val.item())
        if hasattr(val, "tolist"):
            v = val.tolist()
            return int(v[0]) if isinstance(v, list) else int(v)
        return int(val)

    @staticmethod
    def _safe_xyxy(val) -> List[float]:
        """Return [x1, y1, x2, y2] as a plain Python list of floats."""
        if hasattr(val, "tolist"):
            lst = val.tolist()
            # Tensor returns [x1, y1, x2, y2] directly
            if isinstance(lst, list) and len(lst) == 4:
                return [float(v) for v in lst]
        if hasattr(val, "__iter__"):
            return [float(v.item() if hasattr(v, "item") else v) for v in val]
        raise ValueError(f"Cannot convert xyxy value: {val}")

    # ── Drone classification helpers ─────────────────────────────────────────

    def _classify_drone_type(self, w: float, h: float, relative_size: float) -> str:
        """
        FIX-8: micro_drone check moved BEFORE aspect-ratio branches so it
        can actually be reached.
        """
        if relative_size < 0.001:
            return "micro_drone"
        aspect_ratio = w / max(h, 1)
        if aspect_ratio > 2.0:
            return "fixed_wing"
        elif aspect_ratio > 1.3:
            return "quadcopter"
        else:
            return "quadcopter"

    def _estimate_altitude(self, relative_size: float) -> float:
        if relative_size < 0.001:
            return 200.0
        elif relative_size < 0.01:
            return 100.0
        elif relative_size < 0.05:
            return 50.0
        else:
            return 20.0

    @property
    def models_loaded(self) -> bool:
        return self._models_loaded


# ── Mock objects (for testing / no-weights environments) ─────────────────────

class MockYOLOModel:
    """
    Mock YOLO model — generates occasional detections to simulate activity.
    FIX-7: detection_type=None now returns MockEmptyResult, not MockResult(None).
    """

    def __init__(self, detection_type: Optional[str] = None):
        self.detection_type = detection_type
        self._call_count    = 0

    def __call__(self, frame, **kwargs):
        self._call_count += 1
        if self._call_count % 30 == 0 and self.detection_type:
            return [MockResult(frame.shape, self.detection_type)]
        return [MockEmptyResult()]


class MockEmptyResult:
    """Result with no detections."""
    boxes = None


class MockResult:
    def __init__(self, frame_shape, detection_type: str):
        self.boxes = MockBoxes(frame_shape, detection_type)


class MockBoxes:
    """
    FIX-6: Stores plain numpy scalars/arrays matching the interface
    that _parse_yolo_results expects via _safe_float / _safe_int / _safe_xyxy.
    """

    def __init__(self, frame_shape, detection_type: str):
        import random
        h, w = frame_shape[:2]
        x1 = random.uniform(0, w * 0.6)
        y1 = random.uniform(0, h * 0.6)
        x2 = min(x1 + random.uniform(50, 200), w)
        y2 = min(y1 + random.uniform(80, 300), h)
        self.xyxy = [np.array([x1, y1, x2, y2], dtype=np.float32)]
        self.conf = [np.float32(random.uniform(0.65, 0.95))]
        self.cls  = [np.int64(0)]

    def __len__(self):
        return 1
