"""
QuantumFence - Main FastAPI Application
Bug fixes:
  - FIX-11: Calls ensure_directories() at lifespan startup, not import time
  - FIX-22: Added __init__.py imports check; sys.path set before any local imports
"""
import sys
import os

# ── Ensure code/ and code/backend/ are both on the Python path ───────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE_DIR    = os.path.dirname(_BACKEND_DIR)
for _p in (_CODE_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging

from config.settings import settings, ensure_directories
from database.database import engine, Base, SessionLocal
from database.models import Camera, CameraStatus
from api.routes import auth, cameras, alerts, drones, analytics, geofences
from api.websocket import manager
from services.detection_service import DetectionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("quantumfence")

detection_service: DetectionService = None


async def _start_active_cameras(ds: DetectionService) -> None:
    """Load all active cameras from DB on startup and begin detection."""
    db = SessionLocal()
    try:
        active = (
            db.query(Camera)
            .filter(Camera.is_active == True, Camera.status != CameraStatus.DISABLED)
            .all()
        )
        logger.info(f"Auto-starting {len(active)} active camera(s)...")
        for cam in active:
            config = {
                "detect_persons":  cam.detect_persons,
                "detect_vehicles": cam.detect_vehicles,
                "detect_drones":   cam.detect_drones,
            }
            await ds.start_camera(
                camera_id  = cam.id,
                stream_url = cam.stream_url or "simulated",
                config     = config,
            )
    except Exception as e:
        logger.error(f"Error auto-starting cameras: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detection_service

    logger.info("🚀 Starting QuantumFence...")

    # FIX-11: Create directories here, not at settings import time
    ensure_directories()

    # Ensure DB schema
    Base.metadata.create_all(bind=engine)

    # Init detection service + AI models
    detection_service = DetectionService()
    await detection_service.initialize()
    app.state.detection_service = detection_service

    # Auto-start persisted cameras
    await _start_active_cameras(detection_service)

    logger.info("✅ QuantumFence operational")
    yield

    logger.info("🛑 Shutting down QuantumFence...")
    if detection_service:
        await detection_service.shutdown()


app = FastAPI(
    title       = "QuantumFence",
    description = "Quantum-Accelerated Perimeter Defense AI System",
    version     = "1.0.0",
    docs_url    = "/api/docs",
    redoc_url   = "/api/redoc",
    lifespan    = lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Static snapshot serving ─────────────────────────────────────────────────
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
app.mount(
    "/snapshots",
    StaticFiles(directory=settings.SNAPSHOTS_DIR),
    name="snapshots",
)

# ─── API Routers ──────────────────────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api/auth",       tags=["Authentication"])
app.include_router(cameras.router,    prefix="/api/cameras",    tags=["Cameras"])
app.include_router(alerts.router,     prefix="/api/alerts",     tags=["Alerts"])
app.include_router(drones.router,     prefix="/api/drones",     tags=["Drone Detection"])
app.include_router(analytics.router,  prefix="/api/analytics",  tags=["Analytics"])
app.include_router(geofences.router,  prefix="/api/geofences",  tags=["Geofences"])


# ─── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data       = await websocket.receive_json()
            event_type = data.get("type", "ping")

            if event_type == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)

            elif event_type == "subscribe_camera":
                cam_id = data.get("camera_id")
                manager.subscribe_camera(client_id, str(cam_id))
                await manager.send_personal_message(
                    {"type": "subscribed", "camera_id": cam_id}, websocket
                )

            elif event_type == "start_camera":
                # Frontend-triggered camera start
                ds = getattr(app.state, "detection_service", None)
                if ds:
                    await ds.start_camera(
                        data.get("camera_id"),
                        data.get("stream_url", "simulated"),
                        data.get("config", {}),
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
        logger.info(f"WS client disconnected: {client_id}")


# ─── Health & Root ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "system":      "QuantumFence",
        "version":     "1.0.0",
        "status":      "operational",
        "description": "Quantum-Accelerated Perimeter Defense AI System",
    }


@app.get("/health")
async def health():
    ds = getattr(app.state, "detection_service", None)
    return {
        "status":  "healthy",
        "version": "1.0.0",
        "components": {
            "database":       "connected",
            "ai_models":      "loaded" if (ds and ds.model_manager) else "unavailable",
            "detection_service": "running" if ds else "stopped",
            "active_cameras": len(ds.camera_processors) if ds else 0,
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host      = settings.HOST,
        port      = settings.PORT,
        reload    = settings.DEBUG,
        log_level = "info",
    )
