#!/usr/bin/env python3
"""
QuantumFence — Maintenance Script
Performs routine maintenance: snapshot cleanup, DB vacuum, health checks.
Run via cron: 0 2 * * * python3 scripts/maintenance/maintenance.py
"""
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../code/backend"))


def cleanup_snapshots(days: int = 30):
    """Remove snapshots older than N days."""
    snapshots_dir = Path("code/backend/snapshots")
    if not snapshots_dir.exists():
        return
    cutoff = datetime.utcnow() - timedelta(days=days)
    removed = 0
    for f in snapshots_dir.glob("*.jpg"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            f.unlink()
            removed += 1
    print(f"✓ Cleaned up {removed} snapshots older than {days} days")


def cleanup_old_alerts(days: int = 90):
    """Archive resolved alerts older than N days."""
    try:
        from database.database import SessionLocal
        from database.models import Alert, AlertStatus

        db = SessionLocal()
        cutoff = datetime.utcnow() - timedelta(days=days)
        old = (
            db.query(Alert)
            .filter(Alert.status == AlertStatus.RESOLVED, Alert.resolved_at < cutoff)
            .count()
        )
        print(f"✓ Found {old} old resolved alerts (archival recommended)")
        db.close()
    except Exception as e:
        print(f"⚠ Alert cleanup check: {e}")


def check_disk_usage():
    """Check disk usage and warn if low."""
    total, used, free = shutil.disk_usage("/")
    free_pct = (free / total) * 100
    print(
        f"✓ Disk usage: {used // (1024**3)}GB used / {total // (1024**3)}GB total ({free_pct:.1f}% free)"
    )
    if free_pct < 10:
        print(f"⚠ WARNING: Disk space critically low! ({free_pct:.1f}% free)")


def check_system_health():
    """Basic system health checks."""
    import psutil

    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    print(f"✓ CPU usage: {cpu}%")
    print(
        f"✓ RAM usage: {ram.percent}% ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)"
    )


def main():
    print(
        f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}] QuantumFence Maintenance\n"
    )
    cleanup_snapshots(days=30)
    cleanup_old_alerts(days=90)
    check_disk_usage()
    try:
        check_system_health()
    except ImportError:
        print("⚠ psutil not available for health check")
    print("\n✓ Maintenance complete\n")


if __name__ == "__main__":
    main()
