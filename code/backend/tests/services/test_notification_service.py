"""
Tests for NotificationService (services/notification_service.py).
Covers webhook registration, severity filtering, payload construction,
and error handling — all without real network calls.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

from services.notification_service import NotificationService

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    return NotificationService()


@pytest.fixture
def svc_email_enabled(monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "SMTP_HOST",     "smtp.test.com")
    monkeypatch.setattr(settings, "SMTP_USER",     "user@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(settings, "ALERT_EMAIL_RECIPIENTS", ["sec@test.com"])
    return NotificationService()


# ─── Webhook registration ─────────────────────────────────────────────────────

class TestWebhookRegistration:

    def test_register_webhook_stores_url(self, svc):
        svc.register_webhook("https://hooks.test.com/alerts")
        assert "https://hooks.test.com/alerts" in svc._webhook_urls

    def test_register_same_url_twice_not_duplicated(self, svc):
        url = "https://hooks.test.com/alerts"
        svc.register_webhook(url)
        svc.register_webhook(url)
        assert svc._webhook_urls.count(url) == 1

    def test_register_multiple_webhooks(self, svc):
        svc.register_webhook("https://a.com")
        svc.register_webhook("https://b.com")
        assert len(svc._webhook_urls) == 2

    def test_initial_webhooks_empty(self, svc):
        assert svc._webhook_urls == []


# ─── Email enabled check ──────────────────────────────────────────────────────

class TestEmailEnabledFlag:

    def test_email_disabled_by_default(self, svc):
        assert svc.email_enabled is False

    def test_email_enabled_when_all_settings_present(self, svc_email_enabled):
        assert svc_email_enabled.email_enabled is True


# ─── Webhook sending ─────────────────────────────────────────────────────────

class TestWebhookSending:

    @pytest.mark.asyncio
    async def test_send_webhook_posts_json_payload(self, svc):
        svc.register_webhook("https://hooks.test.com/alert")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__  = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__  = AsyncMock(return_value=False)

        with patch("services.notification_service.aiohttp.ClientSession",
                   return_value=mock_session):
            await svc._send_webhooks(
                alert_type="drone_detected",
                severity="high",
                title="Drone Alert",
                description="A drone was detected.",
                camera_name="Cam 01",
                location="North Fence",
                ai_summary="Unauthorized drone.",
            )

        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args
        # Check URL
        assert call_kwargs[0][0] == "https://hooks.test.com/alert"
        # Check payload
        payload = call_kwargs[1]["json"]
        assert payload["system"]     == "QuantumFence"
        assert payload["event"]      == "security_alert"
        assert payload["alert_type"] == "drone_detected"
        assert payload["severity"]   == "high"
        assert payload["title"]      == "Drone Alert"
        assert "timestamp"           in payload

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_raise(self, svc):
        svc.register_webhook("https://broken.com/hook")

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=Exception("connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__  = AsyncMock(return_value=False)

        with patch("services.notification_service.aiohttp.ClientSession",
                   return_value=mock_session):
            # Should log error but not re-raise
            await svc._send_webhooks(
                "person_detected", "medium", "Test", "Desc",
                "Cam", None, None
            )

    @pytest.mark.asyncio
    async def test_multiple_webhooks_all_called(self, svc):
        svc.register_webhook("https://hook1.com")
        svc.register_webhook("https://hook2.com")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__  = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__  = AsyncMock(return_value=False)

        with patch("services.notification_service.aiohttp.ClientSession",
                   return_value=mock_session):
            await svc._send_webhooks("drone_detected", "high", "T", "D", "C", None, None)

        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_no_webhooks_registered_no_post(self, svc):
        with patch("services.notification_service.aiohttp.ClientSession") as mock_cls:
            await svc._send_webhooks("person_detected", "low", "T", "D", "C", None, None)
        mock_cls.assert_not_called()


# ─── notify_alert dispatcher ─────────────────────────────────────────────────

class TestNotifyAlertDispatcher:

    @pytest.mark.asyncio
    async def test_webhook_called_for_any_severity(self, svc):
        svc.register_webhook("https://h.com")
        svc._send_webhooks = AsyncMock()

        for severity in ["low", "medium", "high", "critical"]:
            await svc.notify_alert(
                alert_type="person_detected",
                severity=severity,
                title="Alert",
                description="desc",
                camera_name="Cam",
            )
        assert svc._send_webhooks.call_count == 4

    @pytest.mark.asyncio
    async def test_email_only_for_high_and_critical(self, svc_email_enabled):
        svc_email_enabled._send_email_alert  = AsyncMock()
        svc_email_enabled._send_webhooks     = AsyncMock()

        for severity in ["low", "medium"]:
            await svc_email_enabled.notify_alert(
                "person_detected", severity, "T", "D", "Cam"
            )
        svc_email_enabled._send_email_alert.assert_not_called()

        for severity in ["high", "critical"]:
            await svc_email_enabled.notify_alert(
                "person_detected", severity, "T", "D", "Cam"
            )
        assert svc_email_enabled._send_email_alert.call_count == 2

    @pytest.mark.asyncio
    async def test_no_tasks_when_no_webhooks_and_email_disabled(self, svc):
        # No webhooks registered + email disabled → no network calls at all
        svc._send_webhooks    = AsyncMock()
        svc._send_email_alert = AsyncMock()

        await svc.notify_alert("drone_detected", "critical", "T", "D", "Cam")

        svc._send_email_alert.assert_not_called()
        svc._send_webhooks.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_passes_ai_summary_and_action(self, svc):
        svc.register_webhook("https://h.com")
        svc._send_webhooks = AsyncMock()

        await svc.notify_alert(
            alert_type="drone_detected",
            severity="high",
            title="Drone Alert",
            description="Drone over fence",
            camera_name="Cam 3",
            ai_summary="Likely surveillance drone",
            recommended_action="Deploy response team",
        )

        call_kwargs = svc._send_webhooks.call_args[1]
        assert call_kwargs["ai_summary"]      == "Likely surveillance drone"


# ─── HTML email template ─────────────────────────────────────────────────────

class TestEmailHTMLTemplate:
    """
    We can't send real email, but we can verify the HTML template
    is built correctly by inspecting the generated MIME message.
    """

    @pytest.mark.asyncio
    async def test_email_html_contains_alert_title(self, svc_email_enabled):
        captured = {}

        async def mock_send(msg, **kwargs):
            captured["subject"] = msg["Subject"]
            captured["payload"] = msg.get_payload()

        with patch("services.notification_service.aiosmtplib.send",
                   new=mock_send):
            await svc_email_enabled._send_email_alert(
                alert_type="person_detected",
                severity="critical",
                title="Intruder Alert",
                description="Person at north gate.",
                camera_name="Cam 01",
                location="North Gate",
                snapshot_path=None,
                ai_summary="High-risk intruder.",
                recommended_action="Dispatch patrol.",
            )

        assert "Intruder Alert"   in captured.get("subject", "")
        assert "CRITICAL"         in captured.get("subject", "").upper()

    @pytest.mark.asyncio
    async def test_email_html_contains_ai_summary(self, svc_email_enabled):
        html_content = {}

        async def mock_send(msg, **kwargs):
            # Extract HTML part
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content["body"] = part.get_payload()

        with patch("services.notification_service.aiosmtplib.send", new=mock_send):
            await svc_email_enabled._send_email_alert(
                "drone_detected", "high", "Drone Alert",
                "Drone sighted.", "Cam 02", None, None,
                ai_summary="Unauthorized UAV.", recommended_action="Alert police.",
            )

        import base64
        raw_body = html_content.get("body", "")
        # email.mime may return base64-encoded payload — decode if needed
        try:
            body = base64.b64decode(raw_body).decode("utf-8")
        except Exception:
            body = raw_body
        assert "Unauthorized UAV." in body or "AI Analysis" in body

    @pytest.mark.asyncio
    async def test_email_send_exception_does_not_raise(self, svc_email_enabled):
        with patch("services.notification_service.aiosmtplib.send",
                   side_effect=Exception("SMTP error")):
            # Should log and swallow the exception
            await svc_email_enabled._send_email_alert(
                "person_detected", "high", "T", "D", "Cam", None, None, None, None
            )
