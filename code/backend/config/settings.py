"""
QuantumFence - Application Configuration & Settings
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # ─── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = "QuantumFence"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ─── Security ────────────────────────────────────────────────────────────
    SECRET_KEY: str = "quantum-fence-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./quantumfence.db"

    # ─── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:80",
        "http://127.0.0.1:3000",
    ]

    # ─── AI / Anthropic ──────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-20250514"
    THREAT_ANALYSIS_ENABLED: bool = True
    AI_CONFIDENCE_THRESHOLD: float = 0.65

    # ─── Detection Models ────────────────────────────────────────────────────
    YOLO_MODEL_PATH: str = "ai_models/weights/yolov8n.pt"
    DRONE_MODEL_PATH: str = "ai_models/weights/drone_detector.pt"
    DETECTION_CONFIDENCE: float = 0.5
    DETECTION_IOU_THRESHOLD: float = 0.45
    FRAME_SKIP: int = 3
    MAX_CAMERAS: int = 64
    # Throttle DB last_seen writes to once per N seconds per camera
    TOUCH_CAMERA_INTERVAL_SECONDS: int = 30

    # ─── Geofence ────────────────────────────────────────────────────────────
    DEFAULT_FENCE_BUFFER_METERS: float = 10.0
    GEOFENCE_ALERT_COOLDOWN_SECONDS: int = 30

    # ─── Google Maps / Earth ─────────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_EARTH_ENGINE_PROJECT: str = ""
    DEFAULT_MAP_CENTER_LAT: float = 33.6844
    DEFAULT_MAP_CENTER_LNG: float = 73.0479  # Islamabad, Pakistan

    # ─── Storage ─────────────────────────────────────────────────────────────
    SNAPSHOTS_DIR: str = "snapshots"
    RECORDINGS_DIR: str = "recordings"
    MAX_SNAPSHOT_AGE_DAYS: int = 30

    # ─── Notifications ───────────────────────────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    ALERT_EMAIL_RECIPIENTS: List[str] = []

    # ─── Stream ──────────────────────────────────────────────────────────────
    RTSP_TIMEOUT_SECONDS: int = 10
    STREAM_RECONNECT_ATTEMPTS: int = 3
    STREAM_BUFFER_SIZE: int = 5

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

# FIX: Only create directories at runtime, NOT at import time in tests.
# This is deferred to application startup in main.py lifespan.
# (Previously the bare `os.makedirs` calls here crashed test collection
#  because /tmp paths didn't match monkeypatched settings.)
def ensure_directories() -> None:
    """Create all required runtime directories. Call from main.py lifespan."""
    for d in [settings.SNAPSHOTS_DIR, settings.RECORDINGS_DIR,
              "ai_models/weights", "logs"]:
        os.makedirs(d, exist_ok=True)
