"""
QuantumFence - Drone Detection Module
Advanced UAV/drone detection with trajectory analysis and threat scoring.

Bug fixes:
  - FIX-28: DroneTrack.is_approaching used list comprehension on deque positions
            but checked len(p) >= 4 which is always True for 4-tuples — logic
            simplified and made explicit.
  - FIX-29: detect_swarm() direction_variance calculation — np.var on angles
            wraps around 360°, giving false "no swarm" for N/NW drones.
            Use circular variance instead.
  - FIX-30: _find_nearest_track max_dist parameter was float but default
            matched pixel distances — renamed and documented clearly.
  - FIX-31: DroneTrack positions deque stores 4-tuples (cx,cy,w,h); to_dict
            was trying to access non-existent index on empty deque.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("quantumfence.drone_detector")


@dataclass
class DroneTrack:
    """Represents a tracked drone object over time."""

    track_id: int
    # Each position: (center_x, center_y, bbox_width, bbox_height) in pixels
    positions: deque = field(default_factory=lambda: deque(maxlen=100))
    confidences: deque = field(default_factory=lambda: deque(maxlen=100))
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    drone_type: str = "unknown"
    is_authorized: bool = False
    threat_score: float = 0.0

    @property
    def velocity(self) -> Optional[Tuple[float, float]]:
        if len(self.positions) < 2:
            return None
        p1 = self.positions[-2]
        p2 = self.positions[-1]
        return (p2[0] - p1[0], p2[1] - p1[1])

    @property
    def speed(self) -> float:
        v = self.velocity
        if not v:
            return 0.0
        return math.sqrt(v[0] ** 2 + v[1] ** 2)

    @property
    def trajectory_direction(self) -> Optional[float]:
        v = self.velocity
        if not v:
            return None
        return math.degrees(math.atan2(v[1], v[0]))

    @property
    def is_approaching(self) -> bool:
        """
        FIX-28: detect growing bounding box (drone getting closer).
        Needs ≥5 positions; compares area of first vs last in window.
        """
        if len(self.positions) < 5:
            return False
        recent = list(self.positions)[-5:]
        # Each entry is (cx, cy, w, h)
        areas = [p[2] * p[3] for p in recent]
        return areas[-1] > areas[0]

    def to_dict(self) -> Dict:
        """FIX-31: Guard empty deque before accessing positions[-1]."""
        pos_list = list(self.positions)
        return {
            "track_id": self.track_id,
            "current_position": pos_list[-1] if pos_list else None,
            "trajectory": pos_list,
            "speed": round(self.speed, 2),
            "direction": self.trajectory_direction,
            "is_approaching": self.is_approaching,
            "drone_type": self.drone_type,
            "is_authorized": self.is_authorized,
            "threat_score": round(self.threat_score, 3),
            "duration_seconds": (self.last_seen - self.first_seen).total_seconds(),
            "avg_confidence": (
                round(float(np.mean(list(self.confidences))), 3)
                if self.confidences
                else 0.0
            ),
        }


class DroneDetector:
    """
    Advanced drone detection with multi-object tracking.

    Features:
    - Kalman-style nearest-neighbour tracking
    - Threat scoring based on size, duration, approach vector
    - Swarm detection using circular variance on headings
    - Authorised-zone support
    """

    def __init__(self, confidence_threshold: float = 0.45):
        self.confidence_threshold = confidence_threshold
        self.active_tracks: Dict[int, DroneTrack] = {}
        self._next_track_id = 1
        self._authorized_zones: List[Dict] = []
        self._max_track_age_seconds = 3.0  # seconds of inactivity before pruning

    def process_frame(
        self,
        frame: np.ndarray,
        raw_detections: List[Dict],
    ) -> List[DroneTrack]:
        now = datetime.utcnow()
        valid_dets = [
            d for d in raw_detections if d["confidence"] >= self.confidence_threshold
        ]
        matched_ids = set()

        for det in valid_dets:
            bbox = det.get("bbox", [0, 0, 50, 50])
            cx = bbox[0] + bbox[2] / 2
            cy = bbox[1] + bbox[3] / 2
            pos = (cx, cy, bbox[2], bbox[3])

            best = self._find_nearest_track(cx, cy)
            if best:
                best.positions.append(pos)
                best.confidences.append(det["confidence"])
                best.last_seen = now
                best.threat_score = self._calculate_threat_score(best, frame.shape)
                matched_ids.add(best.track_id)
            else:
                track = DroneTrack(
                    track_id=self._next_track_id,
                    drone_type=det.get("drone_type", "unknown"),
                )
                track.positions.append(pos)
                track.confidences.append(det["confidence"])
                self.active_tracks[self._next_track_id] = track
                matched_ids.add(self._next_track_id)
                self._next_track_id += 1

        # Prune stale tracks
        stale = [
            tid
            for tid, track in self.active_tracks.items()
            if tid not in matched_ids
            and (now - track.last_seen).total_seconds() > self._max_track_age_seconds
        ]
        for tid in stale:
            del self.active_tracks[tid]

        return list(self.active_tracks.values())

    def _find_nearest_track(
        self,
        cx: float,
        cy: float,
        max_dist: float = 150.0,
    ) -> Optional[DroneTrack]:
        """FIX-30: max_dist is in pixels — documented clearly."""
        best = None
        best_dist = max_dist
        for track in self.active_tracks.values():
            if not track.positions:
                continue
            last = track.positions[-1]
            dist = math.sqrt((cx - last[0]) ** 2 + (cy - last[1]) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = track
        return best

    def _calculate_threat_score(self, track: DroneTrack, frame_shape: tuple) -> float:
        score = 0.3

        if track.is_approaching:
            score += 0.25

        if track.speed > 20:
            score += 0.15

        duration = (track.last_seen - track.first_seen).total_seconds()
        if duration > 60:
            score += 0.20
        elif duration > 30:
            score += 0.10

        if track.is_authorized:
            score -= 0.40

        # Proximity to frame centre → likely near facility
        if track.positions and len(frame_shape) >= 2:
            h, w = frame_shape[:2]
            last = track.positions[-1]
            cx_n = last[0] / max(w, 1)
            cy_n = last[1] / max(h, 1)
            centre_dist = math.sqrt((cx_n - 0.5) ** 2 + (cy_n - 0.5) ** 2)
            proximity = 1.0 - min(centre_dist / 0.707, 1.0)
            score += proximity * 0.10

        return min(1.0, max(0.0, score))

    def detect_swarm(self) -> bool:
        """
        FIX-29: Use circular variance so that drones heading ~350° and ~10°
        are correctly identified as "similar direction" (both heading north).
        Returns True when ≥3 drones share a heading (circular var < threshold).
        """
        active = list(self.active_tracks.values())
        if len(active) < 3:
            return False

        directions = [
            t.trajectory_direction for t in active if t.trajectory_direction is not None
        ]
        if len(directions) < 3:
            return False

        # Circular variance: C = mean(cos θ), S = mean(sin θ), R = sqrt(C²+S²)
        # Circular variance V = 1 - R  (0 = all same, 1 = uniform)
        rads = [math.radians(d) for d in directions]
        C = sum(math.cos(r) for r in rads) / len(rads)
        S = sum(math.sin(r) for r in rads) / len(rads)
        R = math.sqrt(C**2 + S**2)
        circ_var = 1.0 - R

        # Low circular variance → drones moving in similar direction → potential swarm
        return circ_var < 0.15

    def add_authorized_zone(self, lat: float, lng: float, radius_m: float):
        self._authorized_zones.append({"lat": lat, "lng": lng, "radius_m": radius_m})

    def get_summary(self) -> Dict:
        tracks = list(self.active_tracks.values())
        high_threat = [t for t in tracks if t.threat_score > 0.7]
        return {
            "active_drones": len(tracks),
            "high_threat_drones": len(high_threat),
            "swarm_detected": self.detect_swarm(),
            "max_threat_score": max((t.threat_score for t in tracks), default=0.0),
            "tracks": [t.to_dict() for t in tracks],
        }
