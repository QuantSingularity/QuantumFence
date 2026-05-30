"""
Tests for AIAnalysisService.
Covers the Claude API integration, response parsing, fallback paths,
and threat level derivation — all without real API calls.
"""

import json
from unittest.mock import MagicMock

import pytest
from services.ai_analysis_service import AIAnalysisService

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def disabled_svc():
    """Service with AI disabled (no API key)."""
    svc = AIAnalysisService()
    svc.enabled = False
    return svc


@pytest.fixture
def enabled_svc():
    """Service with AI enabled but Anthropic client mocked."""
    svc = AIAnalysisService()
    svc.enabled = True
    svc.client = MagicMock()
    return svc


def _make_api_response(json_payload: dict) -> MagicMock:
    """Build a mock Anthropic response object."""
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps(json_payload))]
    return resp


# ─── Disabled-mode (fallback) ─────────────────────────────────────────────────


class TestAIAnalysisDisabled:

    @pytest.mark.asyncio
    async def test_analyze_threat_returns_default(self, disabled_svc):
        result = await disabled_svc.analyze_threat(
            detection_type="person",
            confidence=0.80,
            camera_name="Cam 01",
            camera_location="North Fence",
        )
        assert "threat_level" in result
        assert "risk_score" in result
        assert "summary" in result
        assert "recommended_action" in result

    @pytest.mark.asyncio
    async def test_default_risk_score_scales_with_confidence(self, disabled_svc):
        high = await disabled_svc.analyze_threat("person", 0.95, "Cam", None)
        low = await disabled_svc.analyze_threat("person", 0.30, "Cam", None)
        assert high["risk_score"] > low["risk_score"]

    @pytest.mark.asyncio
    async def test_high_confidence_gives_high_threat(self, disabled_svc):
        result = await disabled_svc.analyze_threat("drone", 0.92, "Cam", None)
        assert result["threat_level"] == "high"

    @pytest.mark.asyncio
    async def test_low_confidence_gives_low_threat(self, disabled_svc):
        result = await disabled_svc.analyze_threat("person", 0.40, "Cam", None)
        assert result["threat_level"] == "low"

    @pytest.mark.asyncio
    async def test_drone_default_analysis_is_high(self, disabled_svc):
        result = await disabled_svc.analyze_drone_threat(
            confidence=0.88,
            drone_type="quadcopter",
            altitude_m=100.0,
            speed_ms=8.0,
            camera_name="Cam 03",
        )
        assert result["threat_level"] == "high"
        assert result["risk_score"] >= 0.7


# ─── Response parsing ─────────────────────────────────────────────────────────


class TestResponseParsing:

    def test_parse_valid_json_response(self, enabled_svc):
        raw = json.dumps(
            {
                "threat_level": "critical",
                "risk_score": 0.95,
                "summary": "Armed intruder detected.",
                "recommended_action": "Deploy response team immediately.",
                "confidence_assessment": "Very high confidence.",
            }
        )
        result = enabled_svc._parse_analysis_response(raw, "person", 0.95)
        assert result["threat_level"] == "critical"
        assert result["risk_score"] == pytest.approx(0.95)
        assert result["summary"] == "Armed intruder detected."
        assert result["recommended_action"] == "Deploy response team immediately."

    def test_parse_json_with_markdown_fences(self, enabled_svc):
        raw = (
            "```json\n"
            + json.dumps(
                {
                    "threat_level": "medium",
                    "risk_score": 0.55,
                    "summary": "Vehicle near perimeter.",
                    "recommended_action": "Monitor closely.",
                }
            )
            + "\n```"
        )
        result = enabled_svc._parse_analysis_response(raw, "vehicle", 0.75)
        assert result["threat_level"] == "medium"

    def test_parse_invalid_json_returns_fallback(self, enabled_svc):
        result = enabled_svc._parse_analysis_response(
            "Not valid JSON !!!", "person", 0.8
        )
        # Must still return a valid dict with required keys
        assert "threat_level" in result
        assert "summary" in result
        assert "recommended_action" in result

    def test_parse_missing_fields_use_defaults(self, enabled_svc):
        raw = json.dumps({"threat_level": "low"})  # missing other fields
        result = enabled_svc._parse_analysis_response(raw, "person", 0.55)
        assert result["threat_level"] == "low"
        assert result["summary"] != ""
        assert result["recommended_action"] != ""

    def test_risk_score_clamped_to_float(self, enabled_svc):
        raw = json.dumps({"threat_level": "high", "risk_score": "0.88"})
        result = enabled_svc._parse_analysis_response(raw, "drone", 0.88)
        assert isinstance(result["risk_score"], float)


# ─── System prompt ────────────────────────────────────────────────────────────


class TestSystemPrompt:

    def test_system_prompt_mentions_quantumfence(self, enabled_svc):
        prompt = enabled_svc._get_system_prompt()
        assert "QuantumFence" in prompt

    def test_system_prompt_mentions_perimeter(self, enabled_svc):
        prompt = enabled_svc._get_system_prompt()
        assert "perimeter" in prompt.lower()

    def test_system_prompt_instructs_json(self, enabled_svc):
        prompt = enabled_svc._get_system_prompt()
        assert "JSON" in prompt


# ─── Threat analysis prompt construction ─────────────────────────────────────


class TestAnalysisPrompt:

    def test_prompt_includes_detection_type(self, enabled_svc):
        p = enabled_svc._build_analysis_prompt(
            "person", 0.80, "Cam 01", "North Gate", {}
        )
        assert "person" in p.lower() or "Person" in p

    def test_prompt_includes_camera_name(self, enabled_svc):
        p = enabled_svc._build_analysis_prompt(
            "vehicle", 0.75, "South Camera", None, {}
        )
        assert "South Camera" in p

    def test_prompt_includes_confidence(self, enabled_svc):
        p = enabled_svc._build_analysis_prompt("drone", 0.91, "Cam", None, {})
        assert "91%" in p or "91.0%" in p or "0.91" in p

    def test_prompt_includes_location_when_provided(self, enabled_svc):
        p = enabled_svc._build_analysis_prompt("person", 0.7, "Cam", "East Tower", {})
        assert "East Tower" in p


# ─── Enabled-mode (mocked API) ────────────────────────────────────────────────


class TestAIAnalysisEnabled:

    @pytest.mark.asyncio
    async def test_analyze_threat_calls_client(self, enabled_svc):
        enabled_svc.client.messages.create.return_value = _make_api_response(
            {
                "threat_level": "high",
                "risk_score": 0.82,
                "summary": "Person breaching perimeter.",
                "recommended_action": "Deploy patrol.",
            }
        )
        result = await enabled_svc.analyze_threat(
            "person", 0.82, "Cam 01", "North Fence"
        )
        assert enabled_svc.client.messages.create.called
        assert result["threat_level"] == "high"

    @pytest.mark.asyncio
    async def test_analyze_drone_threat_calls_client(self, enabled_svc):
        enabled_svc.client.messages.create.return_value = _make_api_response(
            {
                "threat_level": "critical",
                "risk_score": 0.95,
                "drone_purpose": "surveillance",
                "summary": "Surveillance drone hovering.",
                "recommended_action": "Alert authorities.",
            }
        )
        result = await enabled_svc.analyze_drone_threat(
            confidence=0.95,
            drone_type="quadcopter",
            altitude_m=80.0,
            speed_ms=0.5,
            camera_name="Aerial Cam",
        )
        assert result["threat_level"] == "critical"
        assert result["drone_purpose"] == "surveillance"

    @pytest.mark.asyncio
    async def test_api_exception_falls_back_to_default(self, enabled_svc):
        enabled_svc.client.messages.create.side_effect = Exception("API down")
        result = await enabled_svc.analyze_threat("vehicle", 0.75, "Cam", None)
        # Should not raise; should return fallback
        assert "threat_level" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_multiple_threats_analysis(self, enabled_svc):
        enabled_svc.client.messages.create.return_value = _make_api_response(
            {
                "threat_level": "critical",
                "risk_score": 0.97,
                "coordinated_threat": True,
                "summary": "Coordinated attack detected.",
                "recommended_action": "Lockdown immediately.",
            }
        )
        detections = [
            {"type": "person", "confidence": 0.91},
            {"type": "vehicle", "confidence": 0.87},
            {"type": "drone", "confidence": 0.93},
        ]
        result = await enabled_svc.analyze_multiple_threats(detections, "Cam 01")
        assert result["coordinated_threat"] is True
        assert result["threat_level"] == "critical"

    @pytest.mark.asyncio
    async def test_empty_detections_returns_default(self, enabled_svc):
        result = await enabled_svc.analyze_multiple_threats([], "Cam 01")
        assert "threat_level" in result


# ─── Default fallbacks ────────────────────────────────────────────────────────


class TestDefaultFallbacks:

    def test_default_analysis_structure(self, enabled_svc):
        result = enabled_svc._default_analysis("person", 0.78)
        required = [
            "threat_level",
            "risk_score",
            "summary",
            "recommended_action",
            "confidence_assessment",
        ]
        for key in required:
            assert key in result, f"Missing: {key}"

    def test_default_drone_analysis_structure(self, enabled_svc):
        result = enabled_svc._default_drone_analysis(0.90)
        assert result["threat_level"] == "high"
        assert result["risk_score"] >= 0.7
        assert "drone" in result["summary"].lower()

    @pytest.mark.parametrize(
        "confidence,expected_level",
        [
            (0.90, "high"),
            (0.70, "medium"),
            (0.40, "low"),
        ],
    )
    def test_default_threat_level_by_confidence(
        self, enabled_svc, confidence, expected_level
    ):
        result = enabled_svc._default_analysis("person", confidence)
        assert result["threat_level"] == expected_level
