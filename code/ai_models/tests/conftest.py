"""
QuantumFence — AI Models Test Configuration
Located at: code/ai_models/tests/conftest.py

Path resolution:
  - code/ai_models/tests/ → this file
  - code/ai_models/       → parent, contains drone_detector.py, model_manager.py
  - code/                 → grandparent, needed for config.settings
  - code/backend/         → needed for config.settings imports
  All three added to sys.path.
"""
import sys
import os
import pytest
import numpy as np

_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))   # code/ai_models/tests
_AI_DIR      = os.path.dirname(_THIS_DIR)                   # code/ai_models
_CODE_DIR    = os.path.dirname(_AI_DIR)                     # code
_BACKEND_DIR = os.path.join(_CODE_DIR, "backend")           # code/backend

for _p in (_AI_DIR, _CODE_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Set env vars for settings import
os.environ.setdefault("DATABASE_URL",             "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY",               "test-secret")
os.environ.setdefault("ANTHROPIC_API_KEY",        "")
os.environ.setdefault("GOOGLE_MAPS_API_KEY",      "")
os.environ.setdefault("SNAPSHOTS_DIR",            "/tmp/qf_ai_test_snaps")
os.environ.setdefault("THREAT_ANALYSIS_ENABLED",  "false")
os.environ.setdefault("YOLO_MODEL_PATH",          "/tmp/fake_yolo.pt")
os.environ.setdefault("DRONE_MODEL_PATH",         "/tmp/fake_drone.pt")


@pytest.fixture
def blank_frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def noise_frame():
    rng = np.random.default_rng(seed=42)
    return (rng.random((720, 1280, 3)) * 255).astype(np.uint8)


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
