-- QuantumFence — PostgreSQL Initialization Script
-- Runs once when Postgres container first starts

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for text search

-- Set timezone
SET timezone = 'UTC';

-- Create indexes for common queries (additional to SQLAlchemy-managed schema)
-- These run after the app creates its tables

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alerts') THEN
        CREATE INDEX IF NOT EXISTS idx_alerts_status    ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_severity  ON alerts(severity);
        CREATE INDEX IF NOT EXISTS idx_alerts_created   ON alerts(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_detections_ts    ON detections(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_cameras_status   ON cameras(status);
    END IF;
END $$;

COMMENT ON DATABASE quantumfence IS 'QuantumFence — Perimeter Defense AI System Database';
