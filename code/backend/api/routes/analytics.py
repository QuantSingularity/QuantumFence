"""
QuantumFence - Analytics Routes
"""

from datetime import datetime, timedelta

from api.routes.auth import User, get_current_user
from database.database import get_db
from database.models import (
    Alert,
    AlertSeverity,
    AlertType,
    Camera,
    CameraStatus,
    Detection,
    DroneDetection,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    total_cameras = db.query(Camera).count()
    # FIX-23: compare against enum member, not raw string
    online_cameras = (
        db.query(Camera).filter(Camera.status == CameraStatus.ONLINE).count()
    )
    total_alerts = db.query(Alert).filter(Alert.created_at >= last_24h).count()
    critical_alerts = (
        db.query(Alert)
        .filter(
            Alert.created_at >= last_24h,
            Alert.severity == AlertSeverity.CRITICAL,
        )
        .count()
    )
    drone_dets = (
        db.query(DroneDetection).filter(DroneDetection.timestamp >= last_24h).count()
    )
    total_dets = db.query(Detection).filter(Detection.timestamp >= last_24h).count()

    # FIX-24: cap health at 100.0
    system_health = min(
        round((online_cameras / max(total_cameras, 1)) * 100, 1),
        100.0,
    )
    threat_level = (
        "CRITICAL"
        if critical_alerts > 0
        else "HIGH" if total_alerts > 10 else "MEDIUM" if total_alerts > 3 else "CLEAR"
    )

    return {
        "cameras": {
            "total": total_cameras,
            "online": online_cameras,
            "offline": total_cameras - online_cameras,
        },
        "alerts_24h": total_alerts,
        "critical_alerts_24h": critical_alerts,
        "drone_detections_24h": drone_dets,
        "detections_24h": total_dets,
        "threat_level": threat_level,
        "system_health": system_health,
    }


@router.get("/detections/timeline")
async def detections_timeline(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    results = []
    for i in range(days):
        day = since + timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = (
            db.query(Detection)
            .filter(
                Detection.timestamp >= day,
                Detection.timestamp < day_end,
            )
            .count()
        )
        results.append({"date": day.strftime("%Y-%m-%d"), "detections": count})
    return results


@router.get("/alerts/by-type")
async def alerts_by_type(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    return [
        {
            "type": at.value,
            "count": db.query(Alert)
            .filter(
                Alert.created_at >= since,
                Alert.alert_type == at,
            )
            .count(),
        }
        for at in AlertType
    ]


@router.get("/heatmap")
async def get_heatmap_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dets = (
        db.query(Detection)
        .filter(
            Detection.estimated_lat.isnot(None),
            Detection.estimated_lng.isnot(None),
        )
        .limit(1000)
        .all()
    )
    return [
        {
            "lat": d.estimated_lat,
            "lng": d.estimated_lng,
            "weight": d.risk_score or 0.5,
            "type": d.detection_type,
        }
        for d in dets
    ]


@router.get("/cameras/performance")
async def camera_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cameras = db.query(Camera).all()
    return [
        {
            "camera_id": cam.id,
            "name": cam.name,
            "status": cam.status.value if cam.status else "unknown",
            "detections": db.query(Detection)
            .filter(Detection.camera_id == cam.id)
            .count(),
            "alerts": db.query(Alert).filter(Alert.camera_id == cam.id).count(),
        }
        for cam in cameras
    ]
