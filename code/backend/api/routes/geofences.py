"""
QuantumFence - Geofence Management Routes
Bug fixes:
  - FIX-13: _point_in_polygon unified with perimeter_service — coords are [lng,lat]
  - FIX-15: model_validate() instead of from_orm()
  - FIX-18: check-point endpoint reads lat/lng from query params correctly
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import math

from database.database import get_db
from database.models import Geofence
from api.routes.auth import get_current_user, User

router = APIRouter()


class GeofenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    coordinates: list               # [[lng, lat], ...] GeoJSON convention
    fence_type: str = "polygon"
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_meters: Optional[float] = None
    buffer_meters: float = 10.0
    alert_on_entry: bool = True
    alert_on_exit: bool = False
    color: str = "#FF4444"


class GeofenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    coordinates: Optional[list] = None
    buffer_meters: Optional[float] = None
    is_active: Optional[bool] = None
    alert_on_entry: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    color: Optional[str] = None


class GeofenceOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    coordinates: list
    fence_type: str
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_meters: Optional[float] = None
    buffer_meters: float
    is_active: bool
    alert_on_entry: bool
    alert_on_exit: bool
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[GeofenceOut])
async def list_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Geofence).all()


@router.post("/", response_model=GeofenceOut, status_code=201)
async def create_geofence(
    data: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = Geofence(**data.model_dump())
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return gf


@router.get("/{geofence_id}", response_model=GeofenceOut)
async def get_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not gf:
        raise HTTPException(404, "Geofence not found")
    return gf


@router.put("/{geofence_id}", response_model=GeofenceOut)
async def update_geofence(
    geofence_id: int,
    data: GeofenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not gf:
        raise HTTPException(404, "Geofence not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(gf, field, value)
    db.commit()
    db.refresh(gf)
    return gf


@router.delete("/{geofence_id}", status_code=204)
async def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gf = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not gf:
        raise HTTPException(404, "Geofence not found")
    db.delete(gf)
    db.commit()


@router.post("/{geofence_id}/check-point")
async def check_point_in_geofence(
    geofence_id: int,
    lat: float = Query(..., description="Latitude of point to test"),
    lng: float = Query(..., description="Longitude of point to test"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check whether a (lat, lng) point is inside the geofence polygon.
    FIX-18: lat/lng now correctly typed query params (not path params).
    """
    gf = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not gf:
        raise HTTPException(404, "Geofence not found")

    if gf.fence_type == "circle" and gf.center_lat and gf.center_lng:
        inside = _point_in_circle(lat, lng, gf.center_lat, gf.center_lng,
                                  gf.radius_meters or 100.0)
    else:
        inside = _point_in_polygon(lat, lng, gf.coordinates or [])

    return {"inside": inside, "geofence_id": geofence_id, "lat": lat, "lng": lng}


# ─── Geometry helpers (GeoJSON [lng, lat] convention) ────────────────────────

def _point_in_polygon(lat: float, lng: float, coords: list) -> bool:
    """
    Ray-casting algorithm.
    coords = [[lng0,lat0], [lng1,lat1], ...]  (GeoJSON)
    test point = (lat, lng)
    FIX-13: Correct [lng, lat] unpacking.
    """
    if not coords or len(coords) < 3:
        return False
    x, y   = lng, lat
    n      = len(coords)
    inside = False
    p1x, p1y = float(coords[0][0]), float(coords[0][1])
    for i in range(1, n + 1):
        p2x, p2y = float(coords[i % n][0]), float(coords[i % n][1])
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        x_inters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= x_inters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _point_in_circle(
    lat: float, lng: float,
    center_lat: float, center_lng: float,
    radius_m: float,
) -> bool:
    R    = 6_371_000
    phi1 = math.radians(lat)
    phi2 = math.radians(center_lat)
    dphi = math.radians(center_lat - lat)
    dlam = math.radians(center_lng - lng)
    a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return dist <= radius_m
