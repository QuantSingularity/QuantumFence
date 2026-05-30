"""
QuantumFence - Alert Management Routes
Bug fixes:
  - FIX-15: Pydantic v2 model_config instead of class Config
  - FIX-21: /stats route registered BEFORE /{alert_id} to prevent routing collision
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database.database import get_db
from database.models import Alert, AlertType, AlertSeverity, AlertStatus
from api.routes.auth import get_current_user, User

router = APIRouter()


class AlertOut(BaseModel):
    id: int
    camera_id: int
    geofence_id: Optional[int] = None
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: Optional[str] = None
    ai_summary: Optional[str] = None
    recommended_action: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    snapshot_path: Optional[str] = None
    detection_data: Optional[dict] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    notes: Optional[str]          = None


class AlertStats(BaseModel):
    total: int; active: int; acknowledged: int; resolved: int
    critical: int; high: int; medium: int; low: int
    last_24h: int; by_type: dict


# FIX-21: /stats MUST be declared before /{alert_id}
@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since_24h = datetime.utcnow() - timedelta(hours=24)
    by_type   = {
        at.value: db.query(Alert).filter(Alert.alert_type == at).count()
        for at in AlertType
    }
    return AlertStats(
        total        = db.query(Alert).count(),
        active       = db.query(Alert).filter(Alert.status == AlertStatus.ACTIVE).count(),
        acknowledged = db.query(Alert).filter(Alert.status == AlertStatus.ACKNOWLEDGED).count(),
        resolved     = db.query(Alert).filter(Alert.status == AlertStatus.RESOLVED).count(),
        critical     = db.query(Alert).filter(Alert.severity == AlertSeverity.CRITICAL).count(),
        high         = db.query(Alert).filter(Alert.severity == AlertSeverity.HIGH).count(),
        medium       = db.query(Alert).filter(Alert.severity == AlertSeverity.MEDIUM).count(),
        low          = db.query(Alert).filter(Alert.severity == AlertSeverity.LOW).count(),
        last_24h     = db.query(Alert).filter(Alert.created_at >= since_24h).count(),
        by_type      = by_type,
    )


@router.get("/", response_model=List[AlertOut])
async def list_alerts(
    skip: int = 0, limit: int = 50,
    status:     Optional[AlertStatus]   = None,
    severity:   Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType]     = None,
    camera_id:  Optional[int]           = None,
    hours:      Optional[int]           = Query(None, description="Last N hours"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Alert)
    if status:     q = q.filter(Alert.status     == status)
    if severity:   q = q.filter(Alert.severity   == severity)
    if alert_type: q = q.filter(Alert.alert_type == alert_type)
    if camera_id:  q = q.filter(Alert.camera_id  == camera_id)
    if hours:
        q = q.filter(Alert.created_at >= datetime.utcnow() - timedelta(hours=hours))
    return q.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    return a


@router.put("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: int,
    update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    if update.status:
        a.status = update.status
        if update.status == AlertStatus.ACKNOWLEDGED:
            a.acknowledged_by = current_user.id
            a.acknowledged_at = datetime.utcnow()
        elif update.status == AlertStatus.RESOLVED:
            a.resolved_at = datetime.utcnow()
    if update.notes is not None:
        a.notes = update.notes
    db.commit(); db.refresh(a)
    return a


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    a.status          = AlertStatus.ACKNOWLEDGED
    a.acknowledged_by = current_user.id
    a.acknowledged_at = datetime.utcnow()
    db.commit(); db.refresh(a)
    return a


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    a.status      = AlertStatus.RESOLVED
    a.resolved_at = datetime.utcnow()
    db.commit(); db.refresh(a)
    return a


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "Alert not found")
    db.delete(a); db.commit()
