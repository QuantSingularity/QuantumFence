import React, { useState, useEffect, useCallback } from "react";
import { analyticsApi, alertApi, systemApi } from "../services/api";
import { useWebSocket } from "../context/WebSocketContext";

// ── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  icon,
  label,
  value,
  sub,
  color = "var(--qf-cyan)",
  pulse,
}) {
  return (
    <div
      className="qf-card"
      style={{ position: "relative", overflow: "hidden" }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(to right, transparent, ${color}, transparent)`,
        }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--qf-text-muted)",
              letterSpacing: 2,
              marginBottom: 8,
            }}
          >
            {label}
          </div>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 36,
              fontWeight: 900,
              color,
              lineHeight: 1,
              ...(pulse ? { animation: "flicker 2s infinite" } : {}),
            }}
          >
            {value ?? "—"}
          </div>
          {sub && (
            <div
              style={{
                marginTop: 6,
                fontSize: 12,
                color: "var(--qf-text-muted)",
              }}
            >
              {sub}
            </div>
          )}
        </div>
        <div style={{ fontSize: 28, opacity: 0.4 }}>{icon}</div>
      </div>
    </div>
  );
}

// ── Threat Gauge ─────────────────────────────────────────────────────────────
function ThreatGauge({ level }) {
  const map = { CLEAR: 0, LOW: 20, MEDIUM: 50, HIGH: 75, CRITICAL: 100 };
  const colorMap = {
    CLEAR: "var(--qf-green)",
    LOW: "var(--sev-low)",
    MEDIUM: "var(--sev-medium)",
    HIGH: "var(--sev-high)",
    CRITICAL: "var(--sev-critical)",
  };
  const pct = map[level] ?? 0;
  const color = colorMap[level] ?? "var(--qf-green)";
  const r = 56;
  const circ = 2 * Math.PI * r;

  return (
    <div style={{ textAlign: "center", padding: "8px 0" }}>
      <svg
        width={140}
        height={140}
        style={{ display: "block", margin: "0 auto" }}
      >
        {/* Track */}
        <circle
          cx={70}
          cy={70}
          r={r}
          fill="none"
          stroke="var(--qf-border)"
          strokeWidth={8}
        />
        {/* Progress */}
        <circle
          cx={70}
          cy={70}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct / 100)}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
          style={{ transition: "stroke-dashoffset 1s ease, stroke 0.5s" }}
        />
        <text
          x={70}
          y={64}
          textAnchor="middle"
          fontFamily="var(--font-display)"
          fontWeight="900"
          fontSize={pct === 100 ? 11 : 14}
          fill={color}
        >
          {level}
        </text>
        <text
          x={70}
          y={82}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={9}
          fill="var(--qf-text-muted)"
        >
          THREAT LEVEL
        </text>
      </svg>
    </div>
  );
}

// ── Recent Alert Row ─────────────────────────────────────────────────────────
function AlertRow({ alert }) {
  const sev = alert.severity?.toLowerCase();
  const colors = {
    critical: "var(--sev-critical)",
    high: "var(--sev-high)",
    medium: "var(--sev-medium)",
    low: "var(--sev-low)",
  };
  const color = colors[sev] || "var(--qf-text-muted)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        padding: "10px 0",
        borderBottom: "1px solid var(--qf-border)",
        animation: "fade-in-up 0.3s ease",
      }}
    >
      <div
        style={{
          width: 3,
          minHeight: 36,
          borderRadius: 2,
          background: color,
          flexShrink: 0,
          marginTop: 3,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            marginBottom: 2,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {alert.title}
        </div>
        {alert.ai_summary && (
          <div
            style={{
              fontSize: 11,
              color: "var(--qf-text-muted)",
              lineHeight: 1.3,
            }}
          >
            🤖 {alert.ai_summary.slice(0, 70)}
            {alert.ai_summary.length > 70 ? "…" : ""}
          </div>
        )}
        <div
          style={{
            fontSize: 10,
            color: "var(--qf-text-muted)",
            fontFamily: "var(--font-mono)",
            marginTop: 3,
          }}
        >
          CAM {alert.camera_id} ·{" "}
          {new Date(alert.created_at).toLocaleTimeString()}
        </div>
      </div>
      <span className={`badge badge-${sev}`}>{sev}</span>
    </div>
  );
}

// ── Live Event Row ────────────────────────────────────────────────────────────
function EventRow({ ev }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
        padding: "6px 0",
        borderBottom: "1px solid #0d1f3522",
        animation: "fade-in-up 0.2s ease",
      }}
    >
      <span
        style={{ color: ev.color, flexShrink: 0, fontSize: 13, marginTop: 1 }}
      >
        {ev.icon}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 11,
            color: "var(--qf-text-primary)",
            lineHeight: 1.3,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {ev.msg}
        </div>
        <div
          style={{
            fontSize: 9,
            color: "var(--qf-text-muted)",
            fontFamily: "var(--font-mono)",
            marginTop: 1,
          }}
        >
          {ev.time.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [clock, setClock] = useState(new Date());

  const { latestAlert, latestDetection, latestDrone, connected } =
    useWebSocket();

  // Clock
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Load analytics
  const loadData = useCallback(async () => {
    try {
      const [ov, al, health] = await Promise.all([
        analyticsApi.overview(),
        alertApi.list({ limit: 6, status: "active" }),
        systemApi.health().catch(() => null),
      ]);
      setOverview(ov.data);
      setRecentAlerts(al.data);
      if (health) setSystemHealth(health.data);
    } catch (e) {
      console.error("Dashboard load error:", e);
    }
  }, []);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 15000);
    return () => clearInterval(t);
  }, [loadData]);

  // Push WS events into live feed
  const pushEvent = useCallback((icon, color, msg) => {
    setLiveEvents((prev) => [
      { id: Date.now() + Math.random(), icon, color, msg, time: new Date() },
      ...prev.slice(0, 24),
    ]);
  }, []);

  useEffect(() => {
    if (latestAlert)
      pushEvent("⚠", "var(--qf-red)", latestAlert.title || "Security alert");
  }, [latestAlert, pushEvent]);

  useEffect(() => {
    if (latestDrone)
      pushEvent(
        "◈",
        "var(--qf-yellow)",
        `Drone detected · CAM ${latestDrone.camera_id} · ${latestDrone.threat_level?.toUpperCase()}`,
      );
  }, [latestDrone, pushEvent]);

  useEffect(() => {
    if (latestDetection) {
      const det = latestDetection.detections?.[0];
      if (det)
        pushEvent(
          "◉",
          "var(--qf-cyan)",
          `${det.type} detected (${(det.confidence * 100).toFixed(0)}%) · CAM ${latestDetection.camera_id}`,
        );
    }
  }, [latestDetection, pushEvent]);

  const ov = overview;
  const threatLevel = ov?.threat_level || "CLEAR";
  const aiModels = systemHealth?.components?.ai_models || "unknown";
  const activeCams =
    systemHealth?.components?.active_cameras ?? ov?.cameras?.online ?? "—";

  return (
    <div style={{ padding: 28 }}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 28,
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 22,
              fontWeight: 900,
              color: "var(--qf-cyan)",
              letterSpacing: 3,
            }}
          >
            COMMAND CENTER
          </h1>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 4,
            }}
          >
            {clock.toUTCString().replace("GMT", "UTC")}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span
            className={`badge ${connected ? "badge-low" : "badge-critical"}`}
          >
            {connected ? "● LIVE" : "○ CONNECTING"}
          </span>
          <span
            className={`badge ${aiModels === "loaded" ? "badge-low" : "badge-medium"}`}
          >
            AI {aiModels.toUpperCase()}
          </span>
        </div>
      </div>

      {/* ── Top Stats ──────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <StatCard
          icon="◉"
          label="CAMERAS ACTIVE"
          color="var(--qf-green)"
          value={activeCams}
          sub={`of ${ov?.cameras?.total ?? 0} configured`}
        />
        <StatCard
          icon="⚠"
          label="ACTIVE ALERTS"
          color="var(--qf-orange)"
          value={ov?.alerts_24h ?? "—"}
          sub="Last 24 hours"
          pulse={ov?.critical_alerts_24h > 0}
        />
        <StatCard
          icon="◈"
          label="DRONE DETECTIONS"
          color="var(--qf-yellow)"
          value={ov?.drone_detections_24h ?? "—"}
          sub="Last 24 hours"
        />
        <StatCard
          icon="◎"
          label="TOTAL DETECTIONS"
          color="var(--qf-cyan)"
          value={ov?.detections_24h ?? "—"}
          sub="Last 24 hours"
        />
      </div>

      {/* ── Middle Row ─────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "200px 1fr 260px",
          gap: 16,
          marginBottom: 20,
        }}
      >
        {/* Threat gauge */}
        <div
          className="qf-card"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
          }}
        >
          <ThreatGauge level={threatLevel} />
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              SYSTEM HEALTH
            </div>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 26,
                color: "var(--qf-green)",
                marginTop: 4,
              }}
            >
              {ov?.system_health ?? 0}%
            </div>
          </div>
        </div>

        {/* Active alerts panel */}
        <div className="qf-card" style={{ overflow: "hidden" }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--qf-text-muted)",
              letterSpacing: 2,
              marginBottom: 12,
            }}
          >
            ACTIVE THREATS
          </div>
          {recentAlerts.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "28px 0",
                color: "var(--qf-green)",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
              }}
            >
              ✓ NO ACTIVE THREATS
            </div>
          ) : (
            <div style={{ maxHeight: 240, overflowY: "auto" }}>
              {recentAlerts.map((a) => (
                <AlertRow key={a.id} alert={a} />
              ))}
            </div>
          )}
        </div>

        {/* Live event stream */}
        <div className="qf-card" style={{ overflow: "hidden" }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--qf-text-muted)",
              letterSpacing: 2,
              marginBottom: 12,
            }}
          >
            LIVE EVENT STREAM
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto" }}>
            {liveEvents.length === 0 ? (
              <div
                style={{
                  color: "var(--qf-text-muted)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                }}
              >
                Waiting for events…
              </div>
            ) : (
              liveEvents.map((ev) => <EventRow key={ev.id} ev={ev} />)
            )}
          </div>
        </div>
      </div>

      {/* ── Camera Network ─────────────────────────────────────────────────── */}
      <div className="qf-card">
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            letterSpacing: 2,
            marginBottom: 14,
          }}
        >
          CAMERA NETWORK STATUS
        </div>
        {ov?.cameras?.total > 0 ? (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {Array.from({ length: ov.cameras.total }, (_, i) => {
              const isOnline = i < ov.cameras.online;
              return (
                <div
                  key={i}
                  style={{
                    padding: "7px 14px",
                    background: isOnline
                      ? "var(--qf-green-dim)"
                      : "var(--qf-bg-surface)",
                    border: `1px solid ${isOnline ? "var(--qf-green)" : "var(--qf-border)"}`,
                    borderRadius: 6,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: isOnline
                      ? "var(--qf-green)"
                      : "var(--qf-text-muted)",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span
                    className={`status-dot ${isOnline ? "status-online" : "status-offline"}`}
                  />
                  CAM {String(i + 1).padStart(2, "0")}
                </div>
              );
            })}
          </div>
        ) : (
          <div
            style={{
              color: "var(--qf-text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}
          >
            No cameras configured. Go to{" "}
            <a href="/cameras" style={{ color: "var(--qf-cyan)" }}>
              Camera Network
            </a>{" "}
            to add your first camera.
          </div>
        )}
      </div>
    </div>
  );
}
