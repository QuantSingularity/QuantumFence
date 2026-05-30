"""
Tests for the WebSocket ConnectionManager (api/websocket.py).
All WebSocket objects are mocked — no real network needed.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

from api.websocket import ConnectionManager

pytestmark = pytest.mark.unit


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_ws():
    """Return a mock WebSocket object."""
    ws = MagicMock()
    ws.accept      = AsyncMock()
    ws.send_text   = AsyncMock()
    ws.receive_json = AsyncMock()
    return ws


@pytest.fixture
def mgr():
    return ConnectionManager()


# ─── connect / disconnect ────────────────────────────────────────────────────

class TestConnectDisconnect:

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "client_1")
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_stores_client(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "client_1")
        assert "client_1" in mgr.active_connections

    @pytest.mark.asyncio
    async def test_connect_sends_welcome_message(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "client_1")
        ws.send_text.assert_called_once()
        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["type"]      == "connected"
        assert payload["client_id"] == "client_1"

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "client_x")
        mgr.disconnect(ws, "client_x")
        assert "client_x" not in mgr.active_connections

    def test_disconnect_unknown_client_is_safe(self, mgr):
        ws = make_ws()
        mgr.disconnect(ws, "ghost")   # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_clients_connect(self, mgr):
        ws1, ws2 = make_ws(), make_ws()
        await mgr.connect(ws1, "c1")
        await mgr.connect(ws2, "c2")
        assert len(mgr.active_connections) == 2

    @pytest.mark.asyncio
    async def test_connection_count_property(self, mgr):
        ws = make_ws()
        assert mgr.connection_count == 0
        await mgr.connect(ws, "c1")
        assert mgr.connection_count == 1
        mgr.disconnect(ws, "c1")
        assert mgr.connection_count == 0


# ─── Camera subscriptions ────────────────────────────────────────────────────

class TestCameraSubscriptions:

    def test_subscribe_camera(self, mgr):
        mgr.subscribe_camera("client_1", "cam_5")
        assert "client_1" in mgr.camera_subscribers.get("cam_5", set())

    def test_subscribe_multiple_clients_same_camera(self, mgr):
        mgr.subscribe_camera("client_1", "cam_1")
        mgr.subscribe_camera("client_2", "cam_1")
        assert len(mgr.camera_subscribers["cam_1"]) == 2

    def test_unsubscribe_camera(self, mgr):
        mgr.subscribe_camera("client_1", "cam_5")
        mgr.unsubscribe_camera("client_1", "cam_5")
        assert "client_1" not in mgr.camera_subscribers.get("cam_5", set())

    def test_disconnect_removes_from_camera_subscribers(self, mgr):
        ws = MagicMock()
        mgr.active_connections["c1"] = ws
        mgr.subscribe_camera("c1", "cam_3")
        mgr.disconnect(ws, "c1")
        assert "c1" not in mgr.camera_subscribers.get("cam_3", set())

    def test_unsubscribe_nonexistent_is_safe(self, mgr):
        mgr.unsubscribe_camera("nobody", "nocam")   # no raise


# ─── Broadcast ───────────────────────────────────────────────────────────────

class TestBroadcast:

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connected(self, mgr):
        ws1, ws2 = make_ws(), make_ws()
        await mgr.connect(ws1, "c1")
        await mgr.connect(ws2, "c2")
        # Reset call count after connect (which sends a welcome message)
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        await mgr.broadcast({"type": "test", "value": 42})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_payload_is_json_serialised(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "c1")
        ws.send_text.reset_mock()

        msg = {"type": "alert", "data": {"severity": "critical"}}
        await mgr.broadcast(msg)

        raw     = ws.send_text.call_args[0][0]
        decoded = json.loads(raw)
        assert decoded["type"]          == "alert"
        assert decoded["data"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_broadcast_removes_broken_connections(self, mgr):
        ws_good = make_ws()
        ws_bad  = make_ws()
        ws_bad.send_text.side_effect = Exception("connection lost")

        await mgr.connect(ws_good, "good")
        mgr.active_connections["bad"] = ws_bad   # inject directly

        await mgr.broadcast({"type": "test"})

        assert "bad"  not in mgr.active_connections
        assert "good" in    mgr.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections_is_safe(self, mgr):
        await mgr.broadcast({"type": "empty"})   # no raise


# ─── Typed broadcast helpers ─────────────────────────────────────────────────

class TestTypedBroadcasts:

    @pytest.mark.asyncio
    async def test_broadcast_alert_wraps_in_alert_type(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "c1")
        ws.send_text.reset_mock()

        await mgr.broadcast_alert({"id": 7, "severity": "high"})

        raw     = ws.send_text.call_args[0][0]
        decoded = json.loads(raw)
        assert decoded["type"]     == "alert"
        assert decoded["data"]["id"] == 7

    @pytest.mark.asyncio
    async def test_broadcast_detection_type(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "c1")
        ws.send_text.reset_mock()

        await mgr.broadcast_detection({"camera_id": 3})

        decoded = json.loads(ws.send_text.call_args[0][0])
        assert decoded["type"] == "detection"

    @pytest.mark.asyncio
    async def test_broadcast_camera_status(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "c1")
        ws.send_text.reset_mock()

        await mgr.broadcast_camera_status("cam_2", "online")

        decoded = json.loads(ws.send_text.call_args[0][0])
        assert decoded["type"]      == "camera_status"
        assert decoded["camera_id"] == "cam_2"
        assert decoded["status"]    == "online"

    @pytest.mark.asyncio
    async def test_broadcast_drone_detection(self, mgr):
        ws = make_ws()
        await mgr.connect(ws, "c1")
        ws.send_text.reset_mock()

        await mgr.broadcast_drone_detection({"camera_id": 2, "confidence": 0.91})

        decoded = json.loads(ws.send_text.call_args[0][0])
        assert decoded["type"]              == "drone_detection"
        assert decoded["data"]["camera_id"] == 2


# ─── Camera-subscriber broadcast ─────────────────────────────────────────────

class TestBroadcastToCameraSubscribers:

    @pytest.mark.asyncio
    async def test_only_subscribers_receive_message(self, mgr):
        ws_sub  = make_ws()
        ws_other = make_ws()
        await mgr.connect(ws_sub,   "sub")
        await mgr.connect(ws_other, "other")
        mgr.subscribe_camera("sub", "cam_1")
        ws_sub.send_text.reset_mock()
        ws_other.send_text.reset_mock()

        await mgr.broadcast_to_camera_subscribers("cam_1", {"type": "frame"})

        ws_sub.send_text.assert_called_once()
        ws_other.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_subscribers_no_error(self, mgr):
        await mgr.broadcast_to_camera_subscribers("cam_999", {"type": "frame"})

    @pytest.mark.asyncio
    async def test_send_personal_message(self, mgr):
        ws = make_ws()
        await mgr.send_personal_message({"type": "pong"}, ws)
        ws.send_text.assert_called_once()
        decoded = json.loads(ws.send_text.call_args[0][0])
        assert decoded["type"] == "pong"
