"""
QuantumFence - AI Threat Analysis Service
Uses Anthropic Claude API to analyze detections and generate threat assessments.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings

logger = logging.getLogger("quantumfence.ai_analysis")


class AIAnalysisService:
    """Leverages Claude AI to perform intelligent threat analysis."""

    def __init__(self):
        self._client = None  # FIX-9: lazy init
        self.model = settings.AI_MODEL
        self.enabled = settings.THREAT_ANALYSIS_ENABLED and bool(
            settings.ANTHROPIC_API_KEY
        )

    @property
    def client(self):
        """FIX-9: Build the Anthropic client on first use, not at import time."""
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("anthropic package not installed — AI analysis disabled")
                self.enabled = False
        return self._client

    @client.setter
    def client(self, value):
        """Allow tests to inject a mock client directly."""
        self._client = value

    # ── Public analyse methods (all async) ──────────────────────────────────

    async def analyze_threat(
        self,
        detection_type: str,
        confidence: float,
        camera_name: str,
        camera_location: Optional[str],
        additional_context: Optional[Dict] = None,
        snapshot_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return self._default_analysis(detection_type, confidence)

        try:
            import asyncio

            prompt = self._build_analysis_prompt(
                detection_type,
                confidence,
                camera_name,
                camera_location,
                additional_context or {},
            )
            messages = self._build_messages(prompt, snapshot_path)
            # FIX-11: off-load blocking I/O to thread pool
            response = await asyncio.to_thread(self._call_api, messages)
            return self._parse_analysis_response(response, detection_type, confidence)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._default_analysis(detection_type, confidence)

    async def analyze_drone_threat(
        self,
        confidence: float,
        drone_type: Optional[str],
        altitude_m: Optional[float],
        speed_ms: Optional[float],
        camera_name: str,
        snapshot_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return self._default_drone_analysis(confidence)

        try:
            import asyncio

            prompt = (
                f"Analyze this drone detection for a secure perimeter facility:\n\n"
                f"- Confidence: {confidence:.1%}\n"
                f"- Drone Type: {drone_type or 'Unknown'}\n"
                f"- Estimated Altitude: {altitude_m or 'Unknown'} m\n"
                f"- Estimated Speed: {speed_ms or 'Unknown'} m/s\n"
                f"- Camera: {camera_name}\n\n"
                f"Respond in JSON only (no markdown):\n"
                f'{{"threat_level":"low|medium|high|critical",'
                f'"risk_score":0.0-1.0,'
                f'"drone_purpose":"...",'
                f'"summary":"...",'
                f'"recommended_action":"..."}}'
            )
            messages = self._build_messages(prompt, snapshot_path)
            response = await asyncio.to_thread(self._call_api, messages)
            return self._parse_analysis_response(response, "drone_detected", confidence)
        except Exception as e:
            logger.error(f"Drone AI analysis failed: {e}")
            return self._default_drone_analysis(confidence)

    async def analyze_multiple_threats(
        self,
        detections: list,
        camera_name: str,
    ) -> Dict[str, Any]:
        if not self.enabled or not detections:
            return self._default_analysis("multiple_threats", 0.9)

        try:
            import asyncio

            prompt = (
                f'Multiple simultaneous security detections at camera "{camera_name}":\n'
                f"{json.dumps(detections, indent=2)}\n\n"
                f"Assess whether these form a coordinated threat.\n"
                f"Respond in JSON only (no markdown):\n"
                f'{{"threat_level":"...",'
                f'"risk_score":0.0-1.0,'
                f'"coordinated_threat":true|false,'
                f'"summary":"...",'
                f'"recommended_action":"..."}}'
            )
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            response = await asyncio.to_thread(self._call_api, messages)
            return self._parse_analysis_response(response, "multiple_threats", 0.9)
        except Exception as e:
            logger.error(f"Multi-threat analysis failed: {e}")
            return self._default_analysis("multiple_threats", 0.9)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _call_api(self, messages: list) -> str:
        """Blocking Anthropic API call — always run via asyncio.to_thread."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=self._get_system_prompt(),
            messages=messages,
        )
        return response.content[0].text

    def _build_messages(self, prompt: str, snapshot_path: Optional[str]) -> list:
        content: list = []
        if snapshot_path and Path(snapshot_path).exists():
            try:
                import base64

                with open(snapshot_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64,
                        },
                    }
                )
            except Exception as e:
                logger.warning(f"Could not attach snapshot: {e}")
        content.append({"type": "text", "text": prompt})
        return [{"role": "user", "content": content}]

    def _get_system_prompt(self) -> str:
        return (
            "You are QuantumFence AI — an advanced security threat assessment system "
            "for critical infrastructure perimeter protection. You analyse security "
            "camera detections and provide concise, actionable threat assessments.\n\n"
            "IMPORTANT: Respond ONLY with valid JSON — no markdown fences, "
            "no preamble, no trailing text."
        )

    def _build_analysis_prompt(
        self,
        detection_type: str,
        confidence: float,
        camera_name: str,
        camera_location: Optional[str],
        context: dict,
    ) -> str:
        loc = f" at {camera_location}" if camera_location else ""
        return (
            f"Security Detection:\n"
            f"- Camera: {camera_name}{loc}\n"
            f"- Type: {detection_type.replace('_', ' ').title()}\n"
            f"- Confidence: {confidence:.1%}\n"
            f"- Context: {json.dumps(context) if context else 'None'}\n\n"
            f"Respond in JSON only (no markdown):\n"
            f'{{"threat_level":"low|medium|high|critical",'
            f'"risk_score":0.0-1.0,'
            f'"summary":"2-3 sentence assessment",'
            f'"recommended_action":"specific immediate action",'
            f'"confidence_assessment":"brief reliability note"}}'
        )

    def _parse_analysis_response(
        self, raw: str, detection_type: str, confidence: float
    ) -> Dict:
        """
        FIX-10: Strip all markdown fence variants before JSON parsing.
        """
        try:
            # Strip ```json ... ``` or ``` ... ```
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[-1] if clean.count("```") >= 2 else clean
                # Remove leading language tag (json, JSON, etc.)
                lines = clean.split("\n")
                if lines and lines[0].strip().lower() in ("json", ""):
                    lines = lines[1:]
                # Remove trailing fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean = "\n".join(lines).strip()

            data = json.loads(clean)
            return {
                "threat_level": data.get("threat_level", "medium"),
                "risk_score": float(data.get("risk_score", 0.5)),
                "summary": data.get("summary", f"{detection_type} detected."),
                "recommended_action": data.get("recommended_action", "Review feed."),
                "confidence_assessment": data.get("confidence_assessment", ""),
                "drone_purpose": data.get("drone_purpose"),
                "coordinated_threat": bool(data.get("coordinated_threat", False)),
            }
        except Exception as e:
            logger.warning(f"Failed to parse AI response ({e}). Raw: {raw[:200]}")
            return self._default_analysis(detection_type, confidence)

    def _default_analysis(self, detection_type: str, confidence: float) -> Dict:
        level = "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low"
        return {
            "threat_level": level,
            "risk_score": round(confidence * 0.85, 3),
            "summary": (
                f"{detection_type.replace('_', ' ').title()} detected "
                f"with {confidence:.0%} confidence."
            ),
            "recommended_action": "Verify detection and dispatch security if confirmed.",
            "confidence_assessment": f"Model confidence: {confidence:.0%}",
            "drone_purpose": None,
            "coordinated_threat": False,
        }

    def _default_drone_analysis(self, confidence: float) -> Dict:
        return {
            "threat_level": "high",
            "risk_score": round(max(0.7, confidence), 3),
            "summary": (
                f"Unauthorized drone detected with {confidence:.0%} confidence. "
                "Potential surveillance or hostile UAV."
            ),
            "recommended_action": (
                "Alert facility security immediately. "
                "Log drone trajectory and report to authorities."
            ),
            "drone_purpose": "Unknown — treat as hostile until identified.",
            "coordinated_threat": False,
        }
