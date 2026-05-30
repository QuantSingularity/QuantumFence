"""
Tests for GoogleEarthIntegration (integrations/google_earth.py).
Covers KML generation, FOV polygon calculation, detection location
estimation, static map URL generation, and map config endpoint.
"""
import pytest
import math
from unittest.mock import patch
from xml.etree import ElementTree as ET

from integrations.google_earth import GoogleEarthIntegration, GeoPoint, ThreatMarker
from datetime import datetime

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def geo(monkeypatch):
    """Integration instance with no real API keys."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    from config.settings import settings
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")
    return GoogleEarthIntegration()


@pytest.fixture
def geo_with_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "FAKE_KEY_123")
    from config.settings import settings
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "FAKE_KEY_123")
    return GoogleEarthIntegration()


SAMPLE_CAMERAS = [
    {"id": 1, "name": "North Gate",  "latitude": 33.686, "longitude": 73.047,
     "altitude_meters": 5.0, "status": "online",  "location_name": "North",
     "fov_degrees": 90, "direction_degrees": 180},
    {"id": 2, "name": "South Fence", "latitude": 33.682, "longitude": 73.047,
     "altitude_meters": 4.0, "status": "offline", "location_name": "South",
     "fov_degrees": 110, "direction_degrees": 0},
]

SAMPLE_GEOFENCES = [
    {"id": 1, "name": "Outer Perimeter", "description": "Main fence",
     "coordinates": [[73.046, 33.686], [73.050, 33.686],
                     [73.050, 33.682], [73.046, 33.682], [73.046, 33.686]],
     "color": "#FF4444", "is_active": True},
]

SAMPLE_THREATS = [
    ThreatMarker(lat=33.684, lng=73.048, threat_type="drone_detected",
                 severity="high", timestamp=datetime(2024, 1, 1, 12, 0),
                 camera_id=1, description="Drone detected"),
]


# ─── KML generation ───────────────────────────────────────────────────────────

class TestKMLGeneration:

    def test_kml_is_valid_xml(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        # Should not raise
        root = ET.fromstring(kml)
        assert root is not None

    def test_kml_root_tag_is_kml(self, geo):
        kml  = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        root = ET.fromstring(kml)
        # Tag may include namespace
        assert "kml" in root.tag.lower()

    def test_kml_contains_camera_names(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        assert "North Gate"  in kml
        assert "South Fence" in kml

    def test_kml_contains_geofence_name(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        assert "Outer Perimeter" in kml

    def test_kml_contains_threat_markers(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES, SAMPLE_THREATS)
        assert "Drone Detected" in kml or "drone_detected" in kml.lower()

    def test_kml_without_threats_still_valid(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES, threats=None)
        ET.fromstring(kml)   # valid XML

    def test_kml_contains_coordinates_for_cameras(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        assert "73.047" in kml
        assert "33.686" in kml

    def test_kml_empty_cameras_still_valid(self, geo):
        kml = geo.generate_kml([], [], [])
        ET.fromstring(kml)

    def test_kml_style_ids_present(self, geo):
        kml = geo.generate_kml(SAMPLE_CAMERAS, SAMPLE_GEOFENCES)
        assert "camera_online"  in kml
        assert "camera_offline" in kml

    def test_kml_cameras_without_coordinates_skipped(self, geo):
        cams_no_coords = [{"id": 3, "name": "No Location",
                           "latitude": None, "longitude": None,
                           "altitude_meters": 0, "status": "online",
                           "location_name": "", "fov_degrees": 90,
                           "direction_degrees": 0}]
        kml = geo.generate_kml(cams_no_coords, [])
        # No Placemark for camera without coords
        root = ET.fromstring(kml)
        placemarks = root.findall(".//{http://www.opengis.net/kml/2.2}Placemark")
        names = [p.find("{http://www.opengis.net/kml/2.2}name").text for p in placemarks
                 if p.find("{http://www.opengis.net/kml/2.2}name") is not None]
        assert "No Location" not in names


# ─── Camera FOV polygon ───────────────────────────────────────────────────────

class TestCameraFOVPolygon:

    def test_returns_list_of_lat_lng_tuples(self, geo):
        polygon = geo.calculate_camera_fov_polygon(
            lat=33.6844, lng=73.0479,
            direction_deg=0.0, fov_deg=90.0, range_meters=100.0,
        )
        assert isinstance(polygon, list)
        assert len(polygon) >= 3   # at least: origin + 3 arc points + close
        for point in polygon:
            assert len(point) == 2
            lat, lng = point
            assert -90 <= lat <= 90
            assert -180 <= lng <= 180

    def test_fov_polygon_starts_at_camera_location(self, geo):
        lat, lng = 33.6844, 73.0479
        polygon  = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 90.0, 100.0)
        assert polygon[0] == (lat, lng)

    def test_fov_polygon_closes_back_to_camera(self, geo):
        lat, lng = 33.6844, 73.0479
        polygon  = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 90.0, 100.0)
        assert polygon[-1] == (lat, lng)

    def test_wider_fov_spans_more_area(self, geo):
        lat, lng = 33.6844, 73.0479
        narrow = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 30.0,  100.0)
        wide   = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 120.0, 100.0)
        # Collect lngs of right-side points
        narrow_max_lng = max(p[1] for p in narrow)
        wide_max_lng   = max(p[1] for p in wide)
        assert wide_max_lng > narrow_max_lng

    def test_longer_range_places_points_further_away(self, geo):
        lat, lng = 33.6844, 73.0479
        close = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 90.0, 50.0)
        far   = geo.calculate_camera_fov_polygon(lat, lng, 0.0, 90.0, 500.0)

        def max_dist_from_origin(poly):
            return max(
                math.sqrt((p[0] - lat)**2 + (p[1] - lng)**2)
                for p in poly
            )

        assert max_dist_from_origin(far) > max_dist_from_origin(close)


# ─── Detection location estimation ───────────────────────────────────────────

class TestDetectionLocationEstimation:

    def test_returns_lat_lng_tuple(self, geo):
        result = geo.estimate_detection_location(
            camera_lat=33.6844, camera_lng=73.0479,
            camera_direction=0.0, camera_fov=90.0,
            bbox_center_x=0.5, bbox_center_y=0.5,
            estimated_range_m=50.0,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_estimated_location_near_camera(self, geo):
        lat, lng = geo.estimate_detection_location(
            camera_lat=33.6844, camera_lng=73.0479,
            camera_direction=0.0, camera_fov=90.0,
            bbox_center_x=0.5, bbox_center_y=0.5,
            estimated_range_m=100.0,
        )
        # Should be within ~0.01 degrees of camera
        assert abs(lat - 33.6844) < 0.1
        assert abs(lng - 73.0479) < 0.1

    def test_left_bbox_gives_different_lng_than_right(self, geo):
        lat_left, lng_left = geo.estimate_detection_location(
            33.6844, 73.0479, 0.0, 90.0, 0.1, 0.5, 100.0
        )
        lat_right, lng_right = geo.estimate_detection_location(
            33.6844, 73.0479, 0.0, 90.0, 0.9, 0.5, 100.0
        )
        # Different x positions → different longitudes
        assert lng_left != lng_right

    def test_high_in_frame_gives_farther_estimate(self, geo):
        lat_near, lng_near = geo.estimate_detection_location(
            33.6844, 73.0479, 0.0, 90.0, 0.5, 0.9, 100.0   # low in frame
        )
        lat_far, lng_far = geo.estimate_detection_location(
            33.6844, 73.0479, 0.0, 90.0, 0.5, 0.1, 100.0   # high in frame
        )
        dist_near = math.sqrt((lat_near - 33.6844)**2 + (lng_near - 73.0479)**2)
        dist_far  = math.sqrt((lat_far  - 33.6844)**2 + (lng_far  - 73.0479)**2)
        assert dist_far > dist_near


# ─── Static map URL generation ────────────────────────────────────────────────

class TestStaticMapURL:

    def test_no_api_key_returns_openstreetmap_url(self, geo):
        url = geo.generate_static_map_url(SAMPLE_CAMERAS)
        assert "openstreetmap.org" in url

    def test_with_api_key_returns_google_maps_url(self, geo_with_key):
        url = geo_with_key.generate_static_map_url(SAMPLE_CAMERAS)
        assert "maps.googleapis.com" in url
        assert "FAKE_KEY_123" in url

    def test_google_url_includes_camera_markers(self, geo_with_key):
        url = geo_with_key.generate_static_map_url(SAMPLE_CAMERAS)
        assert "markers" in url

    def test_google_url_includes_center(self, geo_with_key):
        url = geo_with_key.generate_static_map_url(SAMPLE_CAMERAS)
        assert "center" in url

    def test_map_type_satellite_by_default(self, geo_with_key):
        url = geo_with_key.generate_static_map_url(SAMPLE_CAMERAS)
        assert "satellite" in url

    def test_cameras_without_coords_excluded_from_markers(self, geo_with_key):
        cams_no_coords = [{"id": 5, "name": "No Loc",
                           "latitude": None, "longitude": None,
                           "status": "online"}]
        # Should not crash
        url = geo_with_key.generate_static_map_url(cams_no_coords)
        assert url != ""


# ─── Map config ───────────────────────────────────────────────────────────────

class TestGetMapConfig:

    def test_map_config_structure(self, geo):
        config = geo.get_map_config()
        for key in ["center", "zoom", "map_type", "use_google_maps", "tile_provider"]:
            assert key in config

    def test_map_config_no_key_uses_openstreetmap(self, geo):
        config = geo.get_map_config()
        assert config["use_google_maps"] is False
        assert config["tile_provider"]   == "openstreetmap"

    def test_map_config_with_key_uses_google(self, geo_with_key):
        config = geo_with_key.get_map_config()
        assert config["use_google_maps"] is True
        assert config["tile_provider"]   == "google"

    def test_map_config_center_matches_settings(self, geo):
        from config.settings import settings
        config = geo.get_map_config()
        assert config["center"]["lat"] == settings.DEFAULT_MAP_CENTER_LAT
        assert config["center"]["lng"] == settings.DEFAULT_MAP_CENTER_LNG


# ─── KML style helper ─────────────────────────────────────────────────────────

class TestKMLStyleHelper:

    def test_style_element_contains_id(self, geo):
        style = geo._kml_style("my_style", "ff00ff00", "camera_icon")
        assert 'id="my_style"' in style

    def test_style_element_contains_color(self, geo):
        style = geo._kml_style("test", "ffaabbcc", "flag")
        assert "ffaabbcc" in style

    def test_geofence_kml_color_is_bbggrr_format(self, geo):
        """KML uses AABBGGRR not AARRGGBB."""
        gf = {**SAMPLE_GEOFENCES[0], "color": "#FF4444"}
        kml = geo._geofence_to_kml(gf)
        # #FF4444 → R=FF G=44 B=44 → KML fill: 80 44 44 FF
        assert "4444ff" in kml.lower()

    def test_geofence_to_kml_returns_string(self, geo):
        result = geo._geofence_to_kml(SAMPLE_GEOFENCES[0])
        assert isinstance(result, str)
        assert "Outer Perimeter" in result

    def test_geofence_to_kml_empty_coords_returns_empty(self, geo):
        result = geo._geofence_to_kml({"coordinates": [], "name": "X"})
        assert result == ""
