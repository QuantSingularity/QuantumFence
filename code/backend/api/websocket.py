"""
QuantumFence - WebSocket Connection Manager
Handles real-time bidirectional communication for live alerts, camera feeds, and detections.
"""

import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("quantumfence.websocket")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.camera_subscribers: Dict[str, Set[str]] = (
            {}
        )  # camera_id -> set of client_ids

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id}")
        await self.send_personal_message(
            {
                "type": "connected",
                "client_id": client_id,
                "message": "Connected to QuantumFence live feed",
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Remove from all camera subscriptions
        for cam_id in list(self.camera_subscribers.keys()):
            self.camera_subscribers[cam_id].discard(client_id)
        logger.info(f"WebSocket client disconnected: {client_id}")

    def subscribe_camera(self, client_id: str, camera_id: str):
        if camera_id not in self.camera_subscribers:
            self.camera_subscribers[camera_id] = set()
        self.camera_subscribers[camera_id].add(client_id)

    def unsubscribe_camera(self, client_id: str, camera_id: str):
        if camera_id in self.camera_subscribers:
            self.camera_subscribers[camera_id].discard(client_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            if client_id in self.active_connections:
                del self.active_connections[client_id]

    async def broadcast_alert(self, alert_data: dict):
        """Broadcast a new alert to all connected clients."""
        await self.broadcast({"type": "alert", "data": alert_data})

    async def broadcast_detection(self, detection_data: dict):
        """Broadcast a detection event to all connected clients."""
        await self.broadcast({"type": "detection", "data": detection_data})

    async def broadcast_camera_status(self, camera_id: str, status: str):
        """Broadcast camera status change."""
        await self.broadcast(
            {"type": "camera_status", "camera_id": camera_id, "status": status}
        )

    async def broadcast_drone_detection(self, drone_data: dict):
        """Broadcast drone detection event."""
        await self.broadcast({"type": "drone_detection", "data": drone_data})

    async def broadcast_to_camera_subscribers(self, camera_id: str, message: dict):
        """Send message only to clients subscribed to a specific camera."""
        subscribers = self.camera_subscribers.get(str(camera_id), set())
        for client_id in subscribers:
            websocket = self.active_connections.get(client_id)
            if websocket:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending to subscriber {client_id}: {e}")

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()
