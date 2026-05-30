"""
QuantumFence - Drone Detection Routes
Bug fixes:
  - FIX-19: DroneOut.from_orm() → model_validate(); Pydantic v2
  - FIX-20: active drones endpoint serializes via model_validate instead of .dict()
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database.database import get_db
from database.models import DroneDetection, ThreatLevel
from api.routes.auth import get_current_user, User

router = APIRouter()


class DroneOut(BaseModel):
    id: int
    camera_id: int
    confidence: float
    bounding_box: Optional[dict] = None
    snapshot_path: Optional[str] = None
    estimated_altitude_m: Optional[float] = None
    estimated_speed_ms: Optional[float] = None
    trajectory_data: Optional[list] = None
    drone_type: Optional[str] = None
    is_authorized: bool
    risk_level: ThreatLevel
    ai_analysis: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[DroneOut])
async def list_drone_detections(
    skip: int = 0,
    limit: int = 50,
    hours: int = 24,
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    q     = db.query(DroneDetection).filter(DroneDetection.timestamp >= since)
    if camera_id:
        q = q.filter(DroneDetection.camera_id == camera_id)
    return q.order_by(DroneDetection.timestamp.desc()).offset(skip).limit(limit).all()


@router.get("/active")
async def get_active_drones(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Drones detected in the last 5 minutes."""
    since  = datetime.utcnow() - timedelta(minutes=5)
    drones = db.query(DroneDetection).filter(DroneDetection.timestamp >= since).all()
    # FIX-20: use model_validate for serialization
    return {
        "active_drones": len(drones),
        "detections":    [DroneOut.model_validate(d).model_dump(mode="json") for d in drones],
    }


@router.get("/stats")
async def drone_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total        = db.query(DroneDetection).count()
    last_24h     = db.query(DroneDetection).filter(
        DroneDetection.timestamp >= datetime.utcnow() - timedelta(hours=24)
    ).count()
    authorized   = db.query(DroneDetection).filter(DroneDetection.is_authorized == True).count()
    unauthorized = total - authorized
    return {
        "total_detections":  total,
        "last_24h":          last_24h,
        "authorized":        authorized,
        "unauthorized":      unauthorized,
        "threat_percentage": round((unauthorized / max(total, 1)) * 100, 1),
    }
