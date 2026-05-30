"""
QuantumFence - Notification Service

Bug fixes:
  - FIX-14: aiosmtplib imported lazily inside _send_email_alert so the module
            can be imported even when aiosmtplib is not installed.
  - FIX-15: aiohttp also imported lazily; avoids startup crash when absent.
"""

import asyncio
import logging
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from config.settings import settings

# Module-level optional imports — tests patch these as module attributes.
# Both are gracefully absent at runtime if not installed.
try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None  # type: ignore

logger = logging.getLogger("quantumfence.notifications")


class NotificationService:
    """Handles all outbound notifications for security alerts."""

    def __init__(self):
        self.email_enabled = all(
            [
                settings.SMTP_HOST,
                settings.SMTP_USER,
                settings.SMTP_PASSWORD,
                settings.ALERT_EMAIL_RECIPIENTS,
            ]
        )
        self._webhook_urls: List[str] = []

    def register_webhook(self, url: str):
        if url not in self._webhook_urls:
            self._webhook_urls.append(url)
            logger.info(f"Webhook registered: {url}")

    async def notify_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        camera_name: str,
        location: Optional[str] = None,
        snapshot_path: Optional[str] = None,
        ai_summary: Optional[str] = None,
        recommended_action: Optional[str] = None,
    ):
        tasks = []
        if self.email_enabled and severity in ("high", "critical"):
            tasks.append(
                self._send_email_alert(
                    alert_type=alert_type,
                    severity=severity,
                    title=title,
                    description=description,
                    camera_name=camera_name,
                    location=location,
                    snapshot_path=snapshot_path,
                    ai_summary=ai_summary,
                    recommended_action=recommended_action,
                )
            )
        if self._webhook_urls:
            tasks.append(
                self._send_webhooks(
                    alert_type=alert_type,
                    severity=severity,
                    title=title,
                    description=description,
                    camera_name=camera_name,
                    location=location,
                    ai_summary=ai_summary,
                )
            )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_email_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        camera_name: str,
        location: Optional[str],
        snapshot_path: Optional[str],
        ai_summary: Optional[str],
        recommended_action: Optional[str],
    ):
        if aiosmtplib is None:
            logger.warning("aiosmtplib not installed — email notifications disabled")
            return

        try:
            sev_color = {
                "low": "#28a745",
                "medium": "#ffc107",
                "high": "#fd7e14",
                "critical": "#dc3545",
            }.get(severity, "#6c757d")

            loc_html = (
                f"<div class='field'><div class='label'>Location</div>"
                f"<div class='value'>{location}</div></div>"
                if location
                else ""
            )
            ai_html = (
                f"<div class='ai-box'><strong>🤖 AI Analysis:</strong><br/>{ai_summary}</div>"
                if ai_summary
                else ""
            )
            act_html = (
                f"<div class='action-box'><strong>⚡ Action:</strong><br/>{recommended_action}</div>"
                if recommended_action
                else ""
            )

            html = f"""<!DOCTYPE html><html><head><style>
body{{font-family:'Segoe UI',sans-serif;background:#0a0a1a;color:#e0e0e0;margin:0}}
.container{{max-width:600px;margin:0 auto;padding:24px}}
.header{{background:linear-gradient(135deg,#0d1b2a,#1a2a4a);padding:24px;
         border-radius:12px 12px 0 0;border-bottom:3px solid {sev_color}}}
.logo{{font-size:24px;font-weight:900;color:#00d4ff;letter-spacing:3px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;
        font-weight:700;background:{sev_color};color:white;text-transform:uppercase}}
.body{{background:#111827;padding:24px}}
.field{{margin-bottom:16px}}
.label{{font-size:11px;text-transform:uppercase;color:#6b7280;letter-spacing:1px;margin-bottom:4px}}
.value{{font-size:15px;color:#e0e0e0}}
.ai-box{{background:#1a2a4a;border-left:4px solid #00d4ff;padding:16px;
          border-radius:0 8px 8px 0;margin:16px 0}}
.action-box{{background:#1a3a1a;border-left:4px solid #00ff88;padding:16px;
              border-radius:0 8px 8px 0}}
.footer{{background:#0d1117;padding:16px;border-radius:0 0 12px 12px;
          text-align:center;font-size:12px;color:#4b5563}}
</style></head><body><div class="container">
<div class="header">
  <div class="logo">⚡ QUANTUMFENCE</div>
  <div style="margin-top:12px">
    <span class="badge">{severity}</span>
    <span style="margin-left:12px;font-size:18px;font-weight:600">{title}</span>
  </div>
</div>
<div class="body">
  <div class="field"><div class="label">Detection Type</div>
    <div class="value">{alert_type.replace('_',' ').title()}</div></div>
  <div class="field"><div class="label">Camera</div>
    <div class="value">{camera_name}</div></div>
  {loc_html}
  <div class="field"><div class="label">Timestamp</div>
    <div class="value">{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</div></div>
  <div class="field"><div class="label">Description</div>
    <div class="value">{description}</div></div>
  {ai_html}{act_html}
</div>
<div class="footer">QuantumFence Security System · Auto-generated alert · Do not reply</div>
</div></body></html>"""

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[QUANTUMFENCE] {severity.upper()} ALERT: {title}"
            msg["From"] = settings.SMTP_USER
            msg["To"] = ", ".join(settings.ALERT_EMAIL_RECIPIENTS)
            msg.attach(MIMEText(html, "html"))

            if snapshot_path and Path(snapshot_path).exists():
                with open(snapshot_path, "rb") as f:
                    img = MIMEImage(f.read())
                    img.add_header(
                        "Content-Disposition", "attachment", filename="detection.jpg"
                    )
                    msg.attach(img)

            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=True,
            )
            logger.info(f"Email alert sent: {title}")

        except Exception as e:
            logger.error(f"Email notification failed: {e}")

    async def _send_webhooks(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        camera_name: str,
        location: Optional[str],
        ai_summary: Optional[str],
    ):
        if not self._webhook_urls:
            return

        if aiohttp is None:
            logger.warning("aiohttp not installed — webhook notifications disabled")
            return

        payload = {
            "system": "QuantumFence",
            "event": "security_alert",
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "camera": camera_name,
            "location": location,
            "ai_summary": ai_summary,
            "timestamp": datetime.utcnow().isoformat(),
        }

        async with aiohttp.ClientSession() as session:
            for url in self._webhook_urls:
                try:
                    async with session.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "X-Source": "QuantumFence",
                        },
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status < 300:
                            logger.info(f"Webhook sent to {url}: {resp.status}")
                        else:
                            logger.warning(f"Webhook non-2xx {url}: {resp.status}")
                except Exception as e:
                    logger.error(f"Webhook error for {url}: {e}")
