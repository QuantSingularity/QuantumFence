#!/usr/bin/env python3
"""
QuantumFence — Database Migration & Seed Script
Run this to initialize DB, apply migrations, and seed demo data.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../code/backend"))

from database.database import engine, Base, SessionLocal
from database.models import User, Camera, Geofence, UserRole, CameraType, CameraStatus
from api.routes.auth import hash_password
from datetime import datetime
import json


def run_migrations():
    print("→ Running database migrations...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database schema created/updated")


def seed_users(db):
    print("→ Seeding users...")
    users = [
        {"username": "admin",    "email": "admin@quantumfence.local",    "password": "quantumfence",  "role": UserRole.ADMIN,    "full_name": "System Administrator"},
        {"username": "operator", "email": "operator@quantumfence.local", "password": "operator123",   "role": UserRole.OPERATOR, "full_name": "Security Operator"},
        {"username": "viewer",   "email": "viewer@quantumfence.local",   "password": "viewer123",     "role": UserRole.VIEWER,   "full_name": "Security Viewer"},
    ]
    for u in users:
        if not db.query(User).filter(User.username == u["username"]).first():
            user = User(
                username=u["username"], email=u["email"],
                hashed_password=hash_password(u["password"]),
                full_name=u["full_name"], role=u["role"], is_active=True
            )
            db.add(user)
            print(f"  + User created: {u['username']} ({u['role'].value})")
        else:
            print(f"  · User exists:  {u['username']}")
    db.commit()


def seed_geofences(db):
    print("→ Seeding geofences...")
    geofences = [
        {
            "name": "Main Facility Perimeter",
            "description": "Outer perimeter boundary of the main facility",
            "coordinates": [
                [73.0469, 33.6854], [73.0489, 33.6854],
                [73.0489, 33.6834], [73.0469, 33.6834],
                [73.0469, 33.6854]
            ],
            "buffer_meters": 15.0,
            "color": "#FF4444",
            "alert_on_entry": True,
        },
        {
            "name": "North Gate Zone",
            "description": "Restricted zone around north gate",
            "coordinates": [
                [73.0472, 33.6852], [73.0480, 33.6852],
                [73.0480, 33.6846], [73.0472, 33.6846],
                [73.0472, 33.6852]
            ],
            "buffer_meters": 5.0,
            "color": "#FF8C00",
            "alert_on_entry": True,
        },
        {
            "name": "Server Room Buffer Zone",
            "description": "High-security zone around server infrastructure",
            "coordinates": [
                [73.0476, 33.6842], [73.0482, 33.6842],
                [73.0482, 33.6838], [73.0476, 33.6838],
                [73.0476, 33.6842]
            ],
            "buffer_meters": 3.0,
            "color": "#FF0000",
            "alert_on_entry": True,
        },
    ]
    for gf in geofences:
        if not db.query(Geofence).filter(Geofence.name == gf["name"]).first():
            geofence = Geofence(**gf, fence_type="polygon", is_active=True)
            db.add(geofence)
            print(f"  + Geofence: {gf['name']}")
        else:
            print(f"  · Exists:   {gf['name']}")
    db.commit()


def seed_cameras(db):
    print("→ Seeding demo cameras...")
    geofence = db.query(Geofence).first()
    cameras = [
        {
            "name": "North Gate Camera",
            "description": "Primary entrance surveillance — north gate",
            "camera_type": CameraType.SIMULATED,
            "stream_url": "simulated",
            "latitude": 33.6852, "longitude": 73.0476,
            "altitude_meters": 4.5, "location_name": "North Entrance",
            "direction_degrees": 180.0, "fov_degrees": 110.0,
            "detect_persons": True, "detect_vehicles": True, "detect_drones": True,
            "resolution_width": 1920, "resolution_height": 1080, "fps": 25,
            "night_vision": True, "status": CameraStatus.ONLINE,
        },
        {
            "name": "South Perimeter Watch",
            "description": "South fence line surveillance",
            "camera_type": CameraType.SIMULATED,
            "stream_url": "simulated",
            "latitude": 33.6836, "longitude": 73.0479,
            "altitude_meters": 6.0, "location_name": "South Fence Line",
            "direction_degrees": 0.0, "fov_degrees": 120.0,
            "detect_persons": True, "detect_vehicles": True, "detect_drones": True,
            "resolution_width": 1920, "resolution_height": 1080, "fps": 30,
            "night_vision": True, "status": CameraStatus.ONLINE,
        },
        {
            "name": "East Aerial Watch",
            "description": "Elevated camera for drone detection — east sector",
            "camera_type": CameraType.SIMULATED,
            "stream_url": "simulated",
            "latitude": 33.6844, "longitude": 73.0488,
            "altitude_meters": 12.0, "location_name": "East Tower",
            "direction_degrees": 270.0, "fov_degrees": 90.0,
            "detect_persons": True, "detect_vehicles": False, "detect_drones": True,
            "resolution_width": 3840, "resolution_height": 2160, "fps": 30,
            "night_vision": False, "ptz_enabled": True, "status": CameraStatus.ONLINE,
        },
        {
            "name": "West Parking Zone",
            "description": "Vehicle monitoring — west parking area",
            "camera_type": CameraType.SIMULATED,
            "stream_url": "simulated",
            "latitude": 33.6844, "longitude": 73.0470,
            "altitude_meters": 5.0, "location_name": "West Parking",
            "direction_degrees": 90.0, "fov_degrees": 100.0,
            "detect_persons": True, "detect_vehicles": True, "detect_drones": False,
            "resolution_width": 1920, "resolution_height": 1080, "fps": 25,
            "night_vision": True, "status": CameraStatus.ONLINE,
        },
    ]
    for c in cameras:
        if not db.query(Camera).filter(Camera.name == c["name"]).first():
            if geofence:
                c["geofence_id"] = geofence.id
            c["last_seen"] = datetime.utcnow()
            camera = Camera(**c)
            db.add(camera)
            print(f"  + Camera: {c['name']}")
        else:
            print(f"  · Exists:  {c['name']}")
    db.commit()


def main():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║     QuantumFence — Database Migration & Seed     ║")
    print("╚══════════════════════════════════════════════════╝\n")

    run_migrations()
    db = SessionLocal()
    try:
        seed_users(db)
        seed_geofences(db)
        seed_cameras(db)
        print("\n✓ Database setup complete!\n")
        print("Default credentials:")
        print("  admin    / quantumfence  (Administrator)")
        print("  operator / operator123   (Operator)")
        print("  viewer   / viewer123     (Viewer)\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
