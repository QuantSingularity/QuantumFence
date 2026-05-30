"""
QuantumFence - SQLAlchemy Database Models
"""

import enum

from database.database import Base
from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# ─── Enums ───────────────────────────────────────────────────────────────────


class CameraType(str, enum.Enum):
    IP_CAMERA = "ip_camera"
    RTSP = "rtsp"
    USB = "usb"
    HTTP_MJPEG = "http_mjpeg"
    SIMULATED = "simulated"


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    INITIALIZING = "initializing"
    DISABLED = "disabled"


class AlertType(str, enum.Enum):
    PERSON_DETECTED = "person_detected"
    VEHICLE_DETECTED = "vehicle_detected"
    DRONE_DETECTED = "drone_detected"
    PERIMETER_BREACH = "perimeter_breach"
    UNKNOWN_OBJECT = "unknown_object"
    MULTIPLE_THREATS = "multiple_threats"
    LOITERING = "loitering"
    FIRE_SMOKE = "fire_smoke"


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class ThreatLevel(str, enum.Enum):
    CLEAR = "clear"
    CAUTION = "caution"
    WARNING = "warning"
    THREAT = "threat"
    CRITICAL = "critical"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ─── Helper: SAEnum with native_enum=False for SQLite ────────────────────────
# FIX-34: SQLite has no native ENUM; store as VARCHAR for portability.
def _enum(e):
    return SAEnum(e, native_enum=False)


# ─── Models ──────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(_enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # FIX-33: explicit back_populates relationship
    alerts_acknowledged = relationship(
        "Alert",
        back_populates="acknowledged_by_user",
        foreign_keys="Alert.acknowledged_by",
    )


class Geofence(Base):
    __tablename__ = "geofences"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    # FIX-32: nullable=True — route validates presence
    coordinates = Column(JSON, nullable=True, default=list)
    fence_type = Column(String(20), default="polygon", nullable=False)
    center_lat = Column(Float)
    center_lng = Column(Float)
    radius_meters = Column(Float)
    buffer_meters = Column(Float, default=10.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    alert_on_entry = Column(Boolean, default=True, nullable=False)
    alert_on_exit = Column(Boolean, default=False, nullable=False)
    color = Column(String(7), default="#FF4444", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cameras = relationship("Camera", back_populates="geofence")
    alerts = relationship("Alert", back_populates="geofence")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    camera_type = Column(_enum(CameraType), default=CameraType.RTSP, nullable=False)
    stream_url = Column(String(500))
    snapshot_url = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)
    altitude_meters = Column(Float, default=0.0, nullable=False)
    location_name = Column(String(200))
    direction_degrees = Column(Float, default=0.0, nullable=False)
    fov_degrees = Column(Float, default=90.0, nullable=False)
    status = Column(
        _enum(CameraStatus), default=CameraStatus.INITIALIZING, nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    detect_persons = Column(Boolean, default=True, nullable=False)
    detect_vehicles = Column(Boolean, default=True, nullable=False)
    detect_drones = Column(Boolean, default=True, nullable=False)
    resolution_width = Column(Integer, default=1920, nullable=False)
    resolution_height = Column(Integer, default=1080, nullable=False)
    fps = Column(Integer, default=25, nullable=False)
    night_vision = Column(Boolean, default=False, nullable=False)
    ptz_enabled = Column(Boolean, default=False, nullable=False)
    geofence_id = Column(Integer, ForeignKey("geofences.id"), nullable=True)
    last_seen = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    geofence = relationship("Geofence", back_populates="cameras")
    alerts = relationship("Alert", back_populates="camera")
    detections = relationship("Detection", back_populates="camera")
    drone_detections = relationship("DroneDetection", back_populates="camera")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    detection_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    bounding_box = Column(JSON)
    object_count = Column(Integer, default=1, nullable=False)
    snapshot_path = Column(String(500))
    threat_level = Column(_enum(ThreatLevel), default=ThreatLevel.CLEAR)
    estimated_lat = Column(Float)
    estimated_lng = Column(Float)
    ai_analysis = Column(Text)
    risk_score = Column(Float, default=0.0, nullable=False)
    # FIX-35: added missing server_default
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    camera = relationship("Camera", back_populates="detections")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    geofence_id = Column(Integer, ForeignKey("geofences.id"), nullable=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=True)
    alert_type = Column(_enum(AlertType), nullable=False)
    severity = Column(
        _enum(AlertSeverity), default=AlertSeverity.MEDIUM, nullable=False
    )
    status = Column(_enum(AlertStatus), default=AlertStatus.ACTIVE, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    ai_summary = Column(Text)
    recommended_action = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    snapshot_path = Column(String(500))
    video_clip_path = Column(String(500))
    detection_data = Column(JSON)
    # FIX-33: explicit FK for acknowledged_by
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    camera = relationship("Camera", back_populates="alerts")
    geofence = relationship("Geofence", back_populates="alerts")
    acknowledged_by_user = relationship(
        "User",
        back_populates="alerts_acknowledged",
        foreign_keys=[acknowledged_by],
    )


class DroneDetection(Base):
    __tablename__ = "drone_detections"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    confidence = Column(Float, nullable=False)
    bounding_box = Column(JSON)
    snapshot_path = Column(String(500))
    estimated_altitude_m = Column(Float)
    estimated_speed_ms = Column(Float)
    trajectory_data = Column(JSON)
    drone_type = Column(String(50))
    is_authorized = Column(Boolean, default=False, nullable=False)
    rf_signature = Column(JSON)
    risk_level = Column(_enum(ThreatLevel), default=ThreatLevel.WARNING, nullable=False)
    ai_analysis = Column(Text)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    camera = relationship("Camera", back_populates="drone_detections")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(10), nullable=False)
    module = Column(String(100))
    message = Column(Text, nullable=False)
    # FIX-36: renamed from 'metadata' (reserved by SQLAlchemy's Base)
    log_metadata = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
