"""
QuantumFence - Google Earth & Maps Integration
Bug fixes:
  - FIX-25: KML color conversion fixed — hex color #RRGGBB → KML AABBGGRR
  - FIX-26: generate_static_map_url builds markers as list (not dict) for urlencode
  - FIX-27: estimate_detection_location protected against division by zero
"""
import logging
import math
import urllib.parse
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field

from config.settings import settings

logger = logging.getLogger("quantumfence.google_earth")


@dataclass
class GeoPoint:
    lat: float
    lng: float
    altitude: float = 0.0
    label: Optional[str] = None


@dataclass
class ThreatMarker:
    lat: float
    lng: float
    threat_type: str
    severity: str
    timestamp: datetime
    camera_id: int
    description: Optional[str] = None


class GoogleEarthIntegration:
    """Integrates QuantumFence with Google Maps/Earth APIs."""

    MAPS_STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"
    GEOCODE_URL     = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self):
        self.api_key     = settings.GOOGLE_MAPS_API_KEY
        self.center_lat  = settings.DEFAULT_MAP_CENTER_LAT
        self.center_lng  = settings.DEFAULT_MAP_CENTER_LNG

    def generate_static_map_url(
        self,
        cameras: List[Dict],
        threats: Optional[List[ThreatMarker]] = None,
        zoom: int = 16,
        size: str = "800x600",
        map_type: str = "satellite",
    ) -> str:
        if not self.api_key:
            return self._generate_osm_url()

        # FIX-26: build params then encode — markers as repeated params
        parts  = [
            f"center={self.center_lat},{self.center_lng}",
            f"zoom={zoom}",
            f"size={size}",
            f"maptype={map_type}",
            f"key={self.api_key}",
        ]

        for cam in cameras:
            lat = cam.get("latitude")
            lng = cam.get("longitude")
            if lat is None or lng is None:
                continue
            color = "blue" if cam.get("status") == "online" else "gray"
            parts.append(f"markers=color:{color}|label:C|{lat},{lng}")

        if threats:
            for t in threats:
                parts.append(f"markers=color:red|label:T|{t.lat},{t.lng}")

        return f"{self.MAPS_STATIC_URL}?{'&'.join(parts)}"

    def _generate_osm_url(self) -> str:
        return (
            f"https://www.openstreetmap.org/?mlat={self.center_lat}"
            f"&mlon={self.center_lng}"
            f"#map=16/{self.center_lat}/{self.center_lng}"
        )

    def generate_kml(
        self,
        cameras: List[Dict],
        geofences: List[Dict],
        threats: Optional[List[ThreatMarker]] = None,
    ) -> str:
        ts    = datetime.utcnow().strftime("%Y-%m-%d")
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            "<Document>",
            f"<name>QuantumFence — Security Map — {ts}</name>",
            "<description>QuantumFence Perimeter Security Visualization</description>",
            self._kml_style("camera_online",  "ff00ff00", "camera_icon"),
            self._kml_style("camera_offline", "ff7a9bb5", "camera_icon"),
            self._kml_style("threat_style",   "ff0000ff", "caution"),
            self._kml_style("drone_style",    "ff00ffff", "airports"),
            "<Folder><name>Security Cameras</name>",
        ]

        for cam in cameras:
            lat = cam.get("latitude")
            lng = cam.get("longitude")
            if lat is None or lng is None:
                continue
            style = "camera_online" if cam.get("status") == "online" else "camera_offline"
            alt   = cam.get("altitude_meters", 0)
            parts.append(
                f"<Placemark>"
                f"<name>{self._xml_escape(cam.get('name', 'Camera'))}</name>"
                f"<description><![CDATA["
                f"Status: {cam.get('status', 'unknown')}<br/>"
                f"Location: {cam.get('location_name', 'Unknown')}<br/>"
                f"FOV: {cam.get('fov_degrees', 90)}° | Dir: {cam.get('direction_degrees', 0)}°"
                f"]]></description>"
                f"<styleUrl>#{style}</styleUrl>"
                f"<Point><coordinates>{lng},{lat},{alt}</coordinates></Point>"
                f"</Placemark>"
            )

        parts.append("</Folder>")

        if geofences:
            parts.append("<Folder><name>Geofences</name>")
            for gf in geofences:
                kml = self._geofence_to_kml(gf)
                if kml:
                    parts.append(kml)
            parts.append("</Folder>")

        if threats:
            parts.append("<Folder><name>Threat Detections</name>")
            for t in threats:
                desc = self._xml_escape(t.description or "Threat detected")
                ts_s = t.timestamp.strftime("%H:%M:%S")
                parts.append(
                    f"<Placemark>"
                    f"<name>{t.threat_type.replace('_', ' ').title()}</name>"
                    f"<description>{desc} — {ts_s}</description>"
                    f"<styleUrl>#threat_style</styleUrl>"
                    f"<Point><coordinates>{t.lng},{t.lat},0</coordinates></Point>"
                    f"</Placemark>"
                )
            parts.append("</Folder>")

        parts.extend(["</Document>", "</kml>"])
        return "\n".join(parts)

    def _kml_style(self, style_id: str, color: str, icon: str) -> str:
        icon_url = f"http://maps.google.com/mapfiles/kml/shapes/{icon}.png"
        return (
            f'<Style id="{style_id}">'
            f"<IconStyle><color>{color}</color><scale>1.2</scale>"
            f"<Icon><href>{icon_url}</href></Icon></IconStyle>"
            f"</Style>"
        )

    def _geofence_to_kml(self, geofence: Dict) -> str:
        coords = geofence.get("coordinates", [])
        if not coords:
            return ""
        # FIX-25: correct #RRGGBB → KML AABBGGRR conversion
        hex_color = geofence.get("color", "#FF4444").lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            # KML fill: 50% opacity → 80BBGGRR
            kml_fill  = f"80{b}{g}{r}"
            # KML line: full opacity → FFBBGGRR
            kml_line  = f"ff{b}{g}{r}"
        else:
            kml_fill  = "80FF4444"
            kml_line  = "ffFF4444"

        # coords = [[lng, lat], ...]
        coord_str = " ".join(f"{c[0]},{c[1]},0" for c in coords)
        name      = self._xml_escape(geofence.get("name", "Geofence"))
        desc      = self._xml_escape(geofence.get("description", ""))
        return (
            f"<Placemark>"
            f"<name>{name}</name>"
            f"<description>{desc}</description>"
            f"<Style>"
            f"<LineStyle><color>{kml_line}</color><width>3</width></LineStyle>"
            f"<PolyStyle><color>{kml_fill}</color></PolyStyle>"
            f"</Style>"
            f"<Polygon><outerBoundaryIs>"
            f"<LinearRing><coordinates>{coord_str}</coordinates></LinearRing>"
            f"</outerBoundaryIs></Polygon>"
            f"</Placemark>"
        )

    def calculate_camera_fov_polygon(
        self,
        lat: float, lng: float,
        direction_deg: float,
        fov_deg: float,
        range_meters: float = 100.0,
    ) -> List[Tuple[float, float]]:
        R         = 6_371_000
        half_fov  = fov_deg / 2
        angles    = [direction_deg - half_fov, direction_deg, direction_deg + half_fov]
        polygon   = [(lat, lng)]

        for angle_deg in angles:
            angle_rad = math.radians(angle_deg)
            lat_r     = math.radians(lat)
            lng_r     = math.radians(lng)
            d         = range_meters / R

            dest_lat_r = math.asin(
                math.sin(lat_r) * math.cos(d)
                + math.cos(lat_r) * math.sin(d) * math.cos(angle_rad)
            )
            dest_lng_r = lng_r + math.atan2(
                math.sin(angle_rad) * math.sin(d) * math.cos(lat_r),
                math.cos(d) - math.sin(lat_r) * math.sin(dest_lat_r),
            )
            polygon.append((math.degrees(dest_lat_r), math.degrees(dest_lng_r)))

        polygon.append((lat, lng))   # close ring
        return polygon

    def estimate_detection_location(
        self,
        camera_lat: float,
        camera_lng: float,
        camera_direction: float,
        camera_fov: float,
        bbox_center_x: float,   # 0.0 – 1.0
        bbox_center_y: float,   # 0.0 – 1.0
        estimated_range_m: float = 50.0,
    ) -> Tuple[float, float]:
        """
        FIX-27: Protect against zero fov or zero range.
        """
        if camera_fov <= 0:
            camera_fov = 90.0
        if estimated_range_m <= 0:
            estimated_range_m = 50.0

        angle_offset = (bbox_center_x - 0.5) * camera_fov
        bearing      = camera_direction + angle_offset
        # Higher in frame → farther away
        range_m      = estimated_range_m * max(0.5, 1.0 + (0.5 - bbox_center_y))

        R         = 6_371_000
        lat_r     = math.radians(camera_lat)
        lng_r     = math.radians(camera_lng)
        bearing_r = math.radians(bearing)
        d         = range_m / R

        dest_lat = math.asin(
            math.sin(lat_r) * math.cos(d)
            + math.cos(lat_r) * math.sin(d) * math.cos(bearing_r)
        )
        dest_lng = lng_r + math.atan2(
            math.sin(bearing_r) * math.sin(d) * math.cos(lat_r),
            math.cos(d) - math.sin(lat_r) * math.sin(dest_lat),
        )
        return math.degrees(dest_lat), math.degrees(dest_lng)

    def get_map_config(self) -> Dict[str, Any]:
        return {
            "center":          {"lat": self.center_lat, "lng": self.center_lng},
            "zoom":            16,
            "map_type":        "satellite",
            "api_key":         self.api_key or None,
            "use_google_maps": bool(self.api_key),
            "tile_provider":   "google" if self.api_key else "openstreetmap",
        }

    @staticmethod
    def _xml_escape(text: str) -> str:
        """Escape special characters for XML/KML content."""
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
        )
