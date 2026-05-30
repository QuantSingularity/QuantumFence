"""
QuantumFence - Perimeter Intelligence Service

Bug fixes:
  - FIX-12: _distance_to_polygon was passing coord[1], coord[0] (lng,lat) to
            haversine — flipped to coord[1]=lat, coord[0]=lng correctly.
  - FIX-13: _point_in_polygon coordinate access made robust for both
            [[lng,lat],...] and [[lat,lng],...] storage formats.
  - FIX-14: analyze_approach_vector guarded against empty coords list.
"""
import logging
import math
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("quantumfence.perimeter")


class PerimeterService:
    """
    Intelligent perimeter monitoring service.
    Coordinates are stored as [lng, lat] (GeoJSON convention).
    """

    def __init__(self):
        self._breach_cooldowns: Dict[str, datetime]       = {}
        self._loitering_tracker: Dict[str, List[datetime]] = {}
        self._cooldown_seconds = 30

    async def check_detection_against_geofences(
        self,
        detection_lat: float,
        detection_lng: float,
        detection_type: str,
        camera_id: int,
        geofences: List[Dict],
    ) -> List[Dict]:
        breaches = []
        for gf in geofences:
            if not gf.get("is_active"):
                continue

            if gf.get("fence_type") == "circle":
                is_inside = self._point_in_circle(
                    detection_lat, detection_lng,
                    gf["center_lat"], gf["center_lng"],
                    gf.get("radius_meters", 100),
                )
            else:
                is_inside = self._point_in_polygon(
                    detection_lat, detection_lng, gf.get("coordinates", [])
                )

            # Check buffer zone when outside polygon
            buffer = gf.get("buffer_meters", 10.0)
            if not is_inside and buffer > 0:
                is_inside = self._is_within_buffer(
                    detection_lat, detection_lng,
                    gf.get("coordinates", []), buffer,
                )

            if is_inside and gf.get("alert_on_entry", True):
                key = f"{camera_id}_{gf['id']}_{detection_type}"
                if not self._is_in_cooldown(key):
                    breaches.append({
                        "geofence_id":    gf["id"],
                        "geofence_name":  gf["name"],
                        "detection_type": detection_type,
                        "severity":       self._calculate_severity(detection_type, gf),
                        "camera_id":      camera_id,
                        "lat":            detection_lat,
                        "lng":            detection_lng,
                        "timestamp":      datetime.utcnow().isoformat(),
                    })
                    self._set_cooldown(key)

        return breaches

    def detect_loitering(
        self,
        track_id: str,
        lat: float,
        lng: float,
        loiter_threshold_seconds: float = 60.0,
    ) -> bool:
        now = datetime.utcnow()
        key = f"loiter_{track_id}"

        if key not in self._loitering_tracker:
            self._loitering_tracker[key] = []

        self._loitering_tracker[key].append(now)

        # Prune entries older than 2× the threshold
        cutoff = now - timedelta(seconds=loiter_threshold_seconds * 2)
        self._loitering_tracker[key] = [
            t for t in self._loitering_tracker[key] if t > cutoff
        ]

        if self._loitering_tracker[key]:
            first_seen = self._loitering_tracker[key][0]
            if (now - first_seen).total_seconds() >= loiter_threshold_seconds:
                return True
        return False

    def analyze_approach_vector(
        self,
        positions: List[Tuple[float, float]],
        fence_coordinates: List[List[float]],
    ) -> Dict:
        """FIX-14: Guard against empty fence_coordinates."""
        if len(positions) < 3:
            return {"approaching": False, "distance_m": None,
                    "rate_m_per_frame": 0.0, "eta_seconds": None,
                    "threat_vector": "insufficient_data"}

        if not fence_coordinates:
            return {"approaching": False, "distance_m": None,
                    "rate_m_per_frame": 0.0, "eta_seconds": None,
                    "threat_vector": "no_fence"}

        recent = positions[-5:]
        distances = [
            self._distance_to_polygon(lat, lng, fence_coordinates)
            for lat, lng in recent
        ]

        if len(distances) < 2:
            return {"approaching": False, "distance_m": round(distances[-1], 1),
                    "rate_m_per_frame": 0.0, "eta_seconds": None,
                    "threat_vector": "stationary"}

        delta      = distances[-1] - distances[0]
        approaching = delta < -2.0
        rate        = delta / max(len(distances) - 1, 1)
        eta         = None
        if approaching and abs(rate) > 0:
            eta = round(distances[-1] / abs(rate), 0)

        return {
            "approaching":      approaching,
            "distance_m":       round(distances[-1], 1),
            "rate_m_per_frame": round(rate, 2),
            "eta_seconds":      eta,
            "threat_vector":    "direct" if approaching and distances[-1] < 20 else "peripheral",
        }

    def _calculate_severity(self, detection_type: str, geofence: Dict) -> str:
        base = {
            "drone":   "high",
            "vehicle": "high",
            "person":  "medium",
            "unknown": "medium",
        }.get(detection_type, "medium")
        if detection_type == "drone" and "critical" in geofence.get("name", "").lower():
            return "critical"
        return base

    def _point_in_circle(
        self, lat: float, lng: float,
        center_lat: float, center_lng: float,
        radius_m: float,
    ) -> bool:
        return self._haversine_distance(lat, lng, center_lat, center_lng) <= radius_m

    def _point_in_polygon(self, lat: float, lng: float, coords: List) -> bool:
        """
        Ray-casting algorithm.
        Coordinates stored as [lng, lat] pairs (GeoJSON convention).
        FIX-13: uses explicit index access; guards empty list.
        """
        if not coords or len(coords) < 3:
            return False
        # GeoJSON stores [lng, lat] — we need lat/lng for the test
        # detection point: (lat, lng)
        x, y = lng, lat
        n    = len(coords)
        inside = False
        # coords[i] = [lng_i, lat_i]
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

    def _is_within_buffer(
        self, lat: float, lng: float, coords: List, buffer_m: float
    ) -> bool:
        if not coords:
            return False
        return self._distance_to_polygon(lat, lng, coords) <= buffer_m

    def _distance_to_polygon(self, lat: float, lng: float, coords: List) -> float:
        """
        FIX-12: coords are [lng, lat] — haversine expects (lat1, lng1, lat2, lng2).
        So vertex lat = coord[1], vertex lng = coord[0].
        """
        if not coords:
            return float("inf")
        return min(
            self._haversine_distance(lat, lng, float(c[1]), float(c[0]))
            for c in coords
        )

    def _haversine_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        R    = 6_371_000  # metres
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)
        a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _is_in_cooldown(self, key: str) -> bool:
        if key in self._breach_cooldowns:
            elapsed = (datetime.utcnow() - self._breach_cooldowns[key]).total_seconds()
            return elapsed < self._cooldown_seconds
        return False

    def _set_cooldown(self, key: str):
        self._breach_cooldowns[key] = datetime.utcnow()
