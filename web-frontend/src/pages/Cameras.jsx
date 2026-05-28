import React, { useState, useEffect, useCallback } from "react";
import { cameraApi } from "../services/api";
import { useWebSocket } from "../context/WebSocketContext";

const CAMERA_TYPES = ["rtsp", "ip_camera", "http_mjpeg", "usb", "simulated"];

// ─── Camera Add/Edit Modal ──────────────────────────────────────────────────
function CameraModal({ camera, onClose, onSave }) {
  const [form, setForm] = useState(
    camera
      ? { ...camera }
      : {
          name: "",
          description: "",
          camera_type: "rtsp",
          stream_url: "",
          latitude: "",
          longitude: "",
          altitude_meters: 0,
          location_name: "",
          direction_degrees: 0,
          fov_degrees: 90,
          detect_persons: true,
          detect_vehicles: true,
          detect_drones: true,
          night_vision: false,
          ptz_enabled: false,
          resolution_width: 1920,
          resolution_height: 1080,
          fps: 25,
        },
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError("Camera name is required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave(form);
      onClose();
    } catch (e) {
      setError(e.response?.data?.detail || "Error saving camera");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#000000cc",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 20,
      }}
    >
      <div
        className="qf-card"
        style={{
          width: "100%",
          maxWidth: 660,
          maxHeight: "90vh",
          overflowY: "auto",
          animation: "fade-in-up 0.25s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 24,
          }}
        >
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 16,
              color: "var(--qf-cyan)",
              letterSpacing: 2,
            }}
          >
            {camera ? "EDIT CAMERA" : "ADD CAMERA"}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--qf-text-muted)",
              cursor: "pointer",
              fontSize: 20,
            }}
          >
            ✕
          </button>
        </div>

        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}
        >
          {/* Name */}
          <div style={{ gridColumn: "1/-1" }}>
            <label className="field-label">CAMERA NAME *</label>
            <input
              className="qf-input"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. North Gate Camera 01"
            />
          </div>

          {/* Type */}
          <div>
            <label className="field-label">CAMERA TYPE</label>
            <select
              className="qf-select"
              style={{ width: "100%" }}
              value={form.camera_type}
              onChange={(e) => set("camera_type", e.target.value)}
            >
              {CAMERA_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          {/* Location name */}
          <div>
            <label className="field-label">LOCATION NAME</label>
            <input
              className="qf-input"
              value={form.location_name || ""}
              onChange={(e) => set("location_name", e.target.value)}
              placeholder="e.g. North Perimeter"
            />
          </div>

          {/* Stream URL */}
          <div style={{ gridColumn: "1/-1" }}>
            <label className="field-label">STREAM URL</label>
            <input
              className="qf-input"
              value={form.stream_url || ""}
              onChange={(e) => set("stream_url", e.target.value)}
              placeholder='rtsp://192.168.1.100:554/stream  (or "simulated" for demo)'
            />
          </div>

          {/* Lat / Lng */}
          <div>
            <label className="field-label">LATITUDE</label>
            <input
              className="qf-input"
              type="number"
              step="0.0001"
              value={form.latitude || ""}
              onChange={(e) => set("latitude", parseFloat(e.target.value))}
              placeholder="33.6844"
            />
          </div>
          <div>
            <label className="field-label">LONGITUDE</label>
            <input
              className="qf-input"
              type="number"
              step="0.0001"
              value={form.longitude || ""}
              onChange={(e) => set("longitude", parseFloat(e.target.value))}
              placeholder="73.0479"
            />
          </div>

          {/* Direction / FOV */}
          <div>
            <label className="field-label">FACING DIRECTION (°)</label>
            <input
              className="qf-input"
              type="number"
              min="0"
              max="360"
              value={form.direction_degrees}
              onChange={(e) =>
                set("direction_degrees", parseFloat(e.target.value))
              }
            />
          </div>
          <div>
            <label className="field-label">FIELD OF VIEW (°)</label>
            <input
              className="qf-input"
              type="number"
              min="10"
              max="360"
              value={form.fov_degrees}
              onChange={(e) => set("fov_degrees", parseFloat(e.target.value))}
            />
          </div>

          {/* Resolution */}
          <div>
            <label className="field-label">RESOLUTION (W × H)</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                className="qf-input"
                type="number"
                value={form.resolution_width}
                onChange={(e) =>
                  set("resolution_width", parseInt(e.target.value))
                }
                placeholder="1920"
              />
              <input
                className="qf-input"
                type="number"
                value={form.resolution_height}
                onChange={(e) =>
                  set("resolution_height", parseInt(e.target.value))
                }
                placeholder="1080"
              />
            </div>
          </div>
          <div>
            <label className="field-label">FPS</label>
            <input
              className="qf-input"
              type="number"
              min="1"
              max="60"
              value={form.fps}
              onChange={(e) => set("fps", parseInt(e.target.value))}
            />
          </div>

          {/* Feature toggles */}
          <div style={{ gridColumn: "1/-1" }}>
            <label
              className="field-label"
              style={{ marginBottom: 10, display: "block" }}
            >
              AI DETECTION FEATURES
            </label>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {[
                { key: "detect_persons", label: "PERSON DETECT" },
                { key: "detect_vehicles", label: "VEHICLE DETECT" },
                { key: "detect_drones", label: "DRONE DETECT" },
                { key: "night_vision", label: "NIGHT VISION" },
                { key: "ptz_enabled", label: "PTZ CONTROL" },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => set(key, !form[key])}
                  style={{
                    padding: "8px 14px",
                    background: form[key]
                      ? "var(--qf-cyan-dim)"
                      : "var(--qf-bg-surface)",
                    border: `1px solid ${form[key] ? "var(--qf-cyan)" : "var(--qf-border)"}`,
                    borderRadius: 6,
                    cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: form[key]
                      ? "var(--qf-cyan)"
                      : "var(--qf-text-muted)",
                    letterSpacing: 1,
                  }}
                >
                  {form[key] ? "■" : "□"} {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div
            style={{
              marginTop: 16,
              background: "var(--qf-red-dim)",
              border: "1px solid var(--qf-red)",
              borderRadius: 8,
              padding: "10px 14px",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "var(--qf-red)",
            }}
          >
            ⚠ {error}
          </div>
        )}

        <div
          style={{
            display: "flex",
            gap: 12,
            marginTop: 24,
            justifyContent: "flex-end",
          }}
        >
          <button className="qf-btn qf-btn-outline" onClick={onClose}>
            CANCEL
          </button>
          <button
            className="qf-btn qf-btn-primary"
            onClick={handleSave}
            disabled={saving || !form.name.trim()}
          >
            {saving ? "SAVING..." : camera ? "UPDATE CAMERA" : "ADD CAMERA"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Camera Stats Modal ─────────────────────────────────────────────────────
function StatsModal({ camera, onClose }) {
  const [stats, setStats] = useState(null);
  const [snapshot, setSnapshot] = useState(null);

  useEffect(() => {
    cameraApi
      .stats(camera.id)
      .then((r) => setStats(r.data))
      .catch(() => {});
    // Try to load the latest snapshot
    const url = `/api/cameras/${camera.id}/snapshot`;
    fetch(url, {
      headers: { Authorization: `Bearer ${localStorage.getItem("qf_token")}` },
    })
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => blob && setSnapshot(URL.createObjectURL(blob)))
      .catch(() => {});
  }, [camera.id]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "#000000cc",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 20,
      }}
    >
      <div
        className="qf-card"
        style={{
          width: "100%",
          maxWidth: 480,
          animation: "fade-in-up 0.2s ease",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <h3
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 14,
              color: "var(--qf-cyan)",
              letterSpacing: 2,
            }}
          >
            CAMERA STATS — {camera.name}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--qf-text-muted)",
              cursor: "pointer",
              fontSize: 18,
            }}
          >
            ✕
          </button>
        </div>

        {/* Latest snapshot */}
        {snapshot && (
          <img
            src={snapshot}
            alt="Latest snapshot"
            style={{
              width: "100%",
              borderRadius: 8,
              marginBottom: 16,
              border: "1px solid var(--qf-border)",
            }}
          />
        )}
        {!snapshot && (
          <div
            style={{
              height: 120,
              background: "var(--qf-bg-surface)",
              borderRadius: 8,
              marginBottom: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px dashed var(--qf-border)",
              color: "var(--qf-text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
            }}
          >
            NO SNAPSHOT YET
          </div>
        )}

        {stats ? (
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
          >
            {[
              ["STATUS", stats.status?.toUpperCase()],
              [
                "LAST SEEN",
                stats.last_seen
                  ? new Date(stats.last_seen).toLocaleTimeString()
                  : "—",
              ],
              ["DETECTIONS", stats.total_detections],
              ["TOTAL ALERTS", stats.total_alerts],
              ["ACTIVE ALERTS", stats.active_alerts],
            ].map(([k, v]) => (
              <div
                key={k}
                style={{
                  background: "var(--qf-bg-surface)",
                  borderRadius: 8,
                  padding: "10px 12px",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    color: "var(--qf-text-muted)",
                    letterSpacing: 1,
                    marginBottom: 4,
                  }}
                >
                  {k}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 15,
                    color: "var(--qf-text-primary)",
                  }}
                >
                  {v}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              textAlign: "center",
              padding: 20,
              color: "var(--qf-text-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            LOADING...
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Camera Card ─────────────────────────────────────────────────────────────
function CameraCard({ camera, onEdit, onDelete, onToggle, onStats }) {
  const statusColors = {
    online: "var(--qf-green)",
    offline: "var(--qf-text-muted)",
    error: "var(--qf-red)",
    initializing: "var(--qf-yellow)",
    disabled: "var(--qf-text-muted)",
  };
  const col = statusColors[camera.status] || "var(--qf-text-muted)";

  return (
    <div
      className="qf-card animate-fade-up"
      style={{ position: "relative", overflow: "hidden" }}
    >
      {/* Top accent bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(to right, transparent, ${col}, transparent)`,
        }}
      />

      {/* Header row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 4,
            }}
          >
            <span
              className={`status-dot ${
                camera.status === "online"
                  ? "status-online"
                  : camera.status === "error"
                    ? "status-error"
                    : "status-offline"
              }`}
            />
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: col,
                letterSpacing: 1,
              }}
            >
              {camera.status?.toUpperCase()}
            </span>
          </div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{camera.name}</div>
          <div
            style={{
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 2,
            }}
          >
            {camera.location_name || "No location set"}
          </div>
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            textAlign: "right",
          }}
        >
          CAM
          <br />
          <span style={{ fontSize: 20, color: "var(--qf-text-secondary)" }}>
            {String(camera.id).padStart(2, "0")}
          </span>
        </div>
      </div>

      {/* Detail grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          marginBottom: 12,
        }}
      >
        {[
          ["TYPE", camera.camera_type?.toUpperCase()],
          ["RES", `${camera.resolution_width}×${camera.resolution_height}`],
          ["FPS", camera.fps],
          ["FOV", `${camera.fov_degrees}°`],
          ["DIR", `${camera.direction_degrees}°`],
          ["ALT", `${camera.altitude_meters}m`],
        ].map(([k, v]) => (
          <div
            key={k}
            style={{
              background: "var(--qf-bg-surface)",
              borderRadius: 6,
              padding: "6px 10px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color: "var(--qf-text-muted)",
                letterSpacing: 1,
              }}
            >
              {k}
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {v}
            </div>
          </div>
        ))}
      </div>

      {/* Detection badges */}
      <div
        style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}
      >
        {camera.detect_persons && (
          <span className="badge badge-low">PERSON</span>
        )}
        {camera.detect_vehicles && (
          <span className="badge badge-medium">VEHICLE</span>
        )}
        {camera.detect_drones && (
          <span className="badge badge-high">DRONE</span>
        )}
        {camera.night_vision && (
          <span
            className="badge"
            style={{
              background: "#bf5af222",
              color: "var(--qf-purple)",
              border: "1px solid #bf5af244",
            }}
          >
            NIGHT
          </span>
        )}
        {camera.ptz_enabled && (
          <span
            className="badge"
            style={{
              background: "#5e5ce622",
              color: "#5e5ce6",
              border: "1px solid #5e5ce644",
            }}
          >
            PTZ
          </span>
        )}
      </div>

      {/* Location coords */}
      {camera.latitude && camera.longitude && (
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            marginBottom: 12,
            padding: "6px 10px",
            background: "var(--qf-bg-surface)",
            borderRadius: 6,
          }}
        >
          📍 {camera.latitude.toFixed(4)}, {camera.longitude.toFixed(4)}
        </div>
      )}

      {/* Actions */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr auto",
          gap: 7,
        }}
      >
        <button
          className="qf-btn qf-btn-outline"
          style={{ fontSize: 10, padding: "8px 4px", justifyContent: "center" }}
          onClick={() => onStats(camera)}
        >
          STATS
        </button>
        <button
          className="qf-btn qf-btn-outline"
          style={{ fontSize: 10, padding: "8px 4px", justifyContent: "center" }}
          onClick={() => onEdit(camera)}
        >
          EDIT
        </button>
        <button
          className="qf-btn"
          style={{
            fontSize: 10,
            padding: "8px 4px",
            justifyContent: "center",
            background: camera.is_active
              ? "var(--qf-red-dim)"
              : "var(--qf-green-dim)",
            border: `1px solid ${camera.is_active ? "var(--qf-red)" : "var(--qf-green)"}`,
            color: camera.is_active ? "var(--qf-red)" : "var(--qf-green)",
          }}
          onClick={() => onToggle(camera)}
        >
          {camera.is_active ? "DISABLE" : "ENABLE"}
        </button>
        <button
          className="qf-btn qf-btn-outline"
          style={{ fontSize: 13, padding: "8px 10px" }}
          onClick={() => onDelete(camera.id)}
          title="Delete camera"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

// ─── Main Cameras Page ───────────────────────────────────────────────────────
export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // null | 'add' | camera_obj
  const [statsFor, setStatsFor] = useState(null); // camera_obj | null
  const [filter, setFilter] = useState("");
  const { cameraStatuses } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const r = await cameraApi.list();
      setCameras(r.data);
    } catch (e) {
      console.error("Camera load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Merge live WebSocket statuses into camera list
  const displayCameras = cameras.map((c) => ({
    ...c,
    status: cameraStatuses[String(c.id)] || c.status,
  }));

  const filtered = displayCameras.filter(
    (c) =>
      !filter ||
      c.name.toLowerCase().includes(filter.toLowerCase()) ||
      c.location_name?.toLowerCase().includes(filter.toLowerCase()) ||
      c.camera_type?.toLowerCase().includes(filter.toLowerCase()),
  );

  const handleSave = async (form) => {
    if (form.id) {
      await cameraApi.update(form.id, form);
    } else {
      await cameraApi.create(form);
    }
    await load();
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this camera and stop its detection stream?")) return;
    await cameraApi.delete(id);
    await load();
  };

  const handleToggle = async (camera) => {
    if (camera.is_active) {
      await cameraApi.disable(camera.id);
    } else {
      await cameraApi.enable(camera.id);
    }
    await load();
  };

  const online = displayCameras.filter((c) => c.status === "online").length;
  const offline = displayCameras.length - online;

  return (
    <div style={{ padding: 28 }}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 20,
              color: "var(--qf-cyan)",
              letterSpacing: 3,
            }}
          >
            CAMERA NETWORK
          </h1>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 4,
            }}
          >
            {cameras.length} cameras &nbsp;·&nbsp;
            <span style={{ color: "var(--qf-green)" }}>
              {online} online
            </span>{" "}
            &nbsp;·&nbsp;
            <span style={{ color: "var(--qf-text-muted)" }}>
              {offline} offline
            </span>
          </div>
        </div>
        <button
          className="qf-btn qf-btn-primary"
          onClick={() => setModal("add")}
        >
          + ADD CAMERA
        </button>
      </div>

      {/* ── Filter ─────────────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 20 }}>
        <input
          className="qf-input"
          style={{ maxWidth: 320 }}
          placeholder="Search by name, location, or type…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {/* ── Grid ────────────────────────────────────────────────────────────── */}
      {loading ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: "var(--qf-text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          LOADING CAMERAS...
        </div>
      ) : filtered.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 80,
            border: "1px dashed var(--qf-border)",
            borderRadius: 16,
            color: "var(--qf-text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 16 }}>◉</div>
          <div>No cameras found.</div>
          <div style={{ marginTop: 8, fontSize: 12 }}>
            Click <strong>+ ADD CAMERA</strong> to register your first camera.
          </div>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))",
            gap: 16,
          }}
        >
          {filtered.map((c) => (
            <CameraCard
              key={c.id}
              camera={c}
              onEdit={(cam) => setModal(cam)}
              onDelete={handleDelete}
              onToggle={handleToggle}
              onStats={(cam) => setStatsFor(cam)}
            />
          ))}
        </div>
      )}

      {/* ── Modals ──────────────────────────────────────────────────────────── */}
      {modal && (
        <CameraModal
          camera={modal === "add" ? null : modal}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
      {statsFor && (
        <StatsModal camera={statsFor} onClose={() => setStatsFor(null)} />
      )}

      {/* Inline style for field labels */}
      <style>{`.field-label{display:block;font-family:var(--font-mono);font-size:10px;color:var(--qf-text-muted);margin-bottom:6px;letter-spacing:1px;text-transform:uppercase}`}</style>
    </div>
  );
}
