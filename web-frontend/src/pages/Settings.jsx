import React, { useState } from "react";
import { systemApi } from "../services/api";
import { useAuth } from "../context/AuthContext";

function Field({ label, defaultValue, type = "text", placeholder }) {
  return (
    <div>
      <label
        style={{
          display: "block",
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--qf-text-muted)",
          marginBottom: 6,
          letterSpacing: 1,
        }}
      >
        {label.toUpperCase()}
      </label>
      <input
        className="qf-input"
        type={type}
        defaultValue={defaultValue}
        placeholder={placeholder || defaultValue || ""}
      />
    </div>
  );
}

function Toggle({ label, defaultOn = false }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <button
      onClick={() => setOn((v) => !v)}
      style={{
        padding: "8px 14px",
        background: on ? "var(--qf-cyan-dim)" : "var(--qf-bg-surface)",
        border: `1px solid ${on ? "var(--qf-cyan)" : "var(--qf-border)"}`,
        borderRadius: 6,
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color: on ? "var(--qf-cyan)" : "var(--qf-text-muted)",
        letterSpacing: 1,
      }}
    >
      {on ? "■" : "□"} {label}
    </button>
  );
}

export default function Settings() {
  const [tab, setTab] = useState("system");
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState(null);
  const { user } = useAuth();

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const checkHealth = async () => {
    try {
      const r = await systemApi.health();
      setHealth(r.data);
    } catch {
      setHealth({ status: "error", message: "Backend not reachable" });
    }
  };

  const TABS = [
    { id: "system", label: "SYSTEM" },
    { id: "ai", label: "AI ENGINE" },
    { id: "notifications", label: "NOTIFICATIONS" },
    { id: "users", label: "USERS" },
    { id: "diagnostics", label: "DIAGNOSTICS" },
  ];

  return (
    <div style={{ padding: 28 }}>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontSize: 20,
          color: "var(--qf-cyan)",
          letterSpacing: 3,
          marginBottom: 24,
        }}
      >
        SYSTEM SETTINGS
      </h1>

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 24,
          borderBottom: "1px solid var(--qf-border)",
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: "10px 20px",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: 1.5,
              color: tab === t.id ? "var(--qf-cyan)" : "var(--qf-text-muted)",
              borderBottom: `2px solid ${tab === t.id ? "var(--qf-cyan)" : "transparent"}`,
              marginBottom: -1,
              transition: "all 0.2s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="qf-card" style={{ maxWidth: 740 }}>
        {/* ── System ────────────────────────────────────────────────────────── */}
        {tab === "system" && (
          <div style={{ display: "grid", gap: 18 }}>
            <h3
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              CORE SYSTEM
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 14,
              }}
            >
              <Field label="Server Host" defaultValue="0.0.0.0" />
              <Field label="Server Port" defaultValue="8000" type="number" />
              <Field label="Worker Processes" defaultValue="4" type="number" />
              <Field label="Max Cameras" defaultValue="64" type="number" />
              <Field label="Frame Skip Rate" defaultValue="3" type="number" />
              <Field
                label="Detection Confidence"
                defaultValue="0.65"
                type="number"
              />
              <Field
                label="Alert Cooldown (sec)"
                defaultValue="30"
                type="number"
              />
              <Field
                label="Snapshot Retention (days)"
                defaultValue="30"
                type="number"
              />
            </div>
            <div>
              <label
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  display: "block",
                  marginBottom: 8,
                }}
              >
                ALLOWED ORIGINS (comma-separated)
              </label>
              <input
                className="qf-input"
                defaultValue="http://localhost:3000,http://localhost:5173"
              />
            </div>
          </div>
        )}

        {/* ── AI Engine ─────────────────────────────────────────────────────── */}
        {tab === "ai" && (
          <div style={{ display: "grid", gap: 18 }}>
            <h3
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              AI ENGINE CONFIGURATION
            </h3>
            <Field
              label="Anthropic API Key"
              type="password"
              placeholder="sk-ant-…"
            />
            <Field
              label="Claude Model"
              defaultValue="claude-sonnet-4-20250514"
            />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 14,
              }}
            >
              <Field
                label="Google Maps API Key"
                type="password"
                placeholder="AIza…"
              />
              <Field
                label="Google Earth Project"
                placeholder="your-gee-project-id"
              />
              <Field
                label="YOLO Model Path"
                defaultValue="ai_models/weights/yolov8n.pt"
              />
              <Field
                label="Drone Model Path"
                defaultValue="ai_models/weights/drone_detector.pt"
              />
              <Field
                label="AI Confidence Threshold"
                defaultValue="0.65"
                type="number"
              />
              <Field
                label="Detection IOU Threshold"
                defaultValue="0.45"
                type="number"
              />
            </div>
            <div>
              <label
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  display: "block",
                  marginBottom: 10,
                }}
              >
                FEATURES
              </label>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <Toggle label="AI THREAT ANALYSIS" defaultOn={true} />
                <Toggle label="DRONE CLASSIFICATION" defaultOn={true} />
                <Toggle label="MULTI-THREAT DETECT" defaultOn={true} />
                <Toggle label="LOITERING DETECTION" defaultOn={true} />
                <Toggle label="SWARM DETECTION" defaultOn={true} />
              </div>
            </div>
          </div>
        )}

        {/* ── Notifications ─────────────────────────────────────────────────── */}
        {tab === "notifications" && (
          <div style={{ display: "grid", gap: 18 }}>
            <h3
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              NOTIFICATION SETTINGS
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 14,
              }}
            >
              <Field label="SMTP Host" defaultValue="smtp.gmail.com" />
              <Field label="SMTP Port" defaultValue="587" type="number" />
              <Field
                label="SMTP Username"
                type="email"
                placeholder="alerts@yourdomain.com"
              />
              <Field label="SMTP Password" type="password" />
            </div>
            <Field
              label="Alert Recipients (comma-separated)"
              placeholder="sec@domain.com,ops@domain.com"
            />
            <Field
              label="Webhook URL"
              type="url"
              placeholder="https://hooks.slack.com/…"
            />
            <div>
              <label
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  display: "block",
                  marginBottom: 10,
                }}
              >
                ALERT ON SEVERITY
              </label>
              <div style={{ display: "flex", gap: 10 }}>
                <Toggle label="CRITICAL" defaultOn={true} />
                <Toggle label="HIGH" defaultOn={true} />
                <Toggle label="MEDIUM" defaultOn={false} />
                <Toggle label="LOW" defaultOn={false} />
              </div>
            </div>
          </div>
        )}

        {/* ── Users ─────────────────────────────────────────────────────────── */}
        {tab === "users" && (
          <div style={{ display: "grid", gap: 18 }}>
            <h3
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              CREATE NEW USER
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 14,
              }}
            >
              <Field label="Username" />
              <Field label="Full Name" />
              <Field label="Email" type="email" />
              <Field label="Password" type="password" />
            </div>
            <div>
              <label
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  display: "block",
                  marginBottom: 6,
                }}
              >
                ROLE
              </label>
              <select className="qf-select" style={{ width: "100%" }}>
                {["admin", "operator", "viewer"].map((r) => (
                  <option key={r} value={r}>
                    {r.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="qf-btn qf-btn-primary"
              style={{ justifyContent: "center" }}
            >
              + CREATE USER
            </button>

            <hr
              style={{
                border: "none",
                borderTop: "1px solid var(--qf-border)",
                margin: "4px 0",
              }}
            />
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color: "var(--qf-text-muted)",
                letterSpacing: 1,
              }}
            >
              LOGGED IN AS:{" "}
              <span style={{ color: "var(--qf-cyan)" }}>
                {user?.username?.toUpperCase()}
              </span>{" "}
              &nbsp;·&nbsp; ROLE:{" "}
              <span style={{ color: "var(--qf-cyan)" }}>
                {user?.role?.toUpperCase()}
              </span>
            </div>
          </div>
        )}

        {/* ── Diagnostics ───────────────────────────────────────────────────── */}
        {tab === "diagnostics" && (
          <div style={{ display: "grid", gap: 18 }}>
            <h3
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--qf-text-muted)",
                letterSpacing: 2,
              }}
            >
              SYSTEM DIAGNOSTICS
            </h3>
            <button
              className="qf-btn qf-btn-outline"
              style={{ width: "fit-content", fontSize: 12 }}
              onClick={checkHealth}
            >
              ↻ CHECK BACKEND HEALTH
            </button>
            {health && (
              <div
                style={{
                  background: "var(--qf-bg-surface)",
                  borderRadius: 10,
                  padding: 16,
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              >
                <div
                  style={{
                    marginBottom: 10,
                    color:
                      health.status === "healthy"
                        ? "var(--qf-green)"
                        : "var(--qf-red)",
                    fontWeight: 700,
                    fontSize: 14,
                  }}
                >
                  {health.status === "healthy"
                    ? "✓ BACKEND HEALTHY"
                    : "✗ BACKEND ERROR"}
                </div>
                {health.components &&
                  Object.entries(health.components).map(([k, v]) => (
                    <div
                      key={k}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: 7,
                        borderBottom: "1px solid var(--qf-border)",
                        paddingBottom: 7,
                      }}
                    >
                      <span
                        style={{
                          color: "var(--qf-text-muted)",
                          letterSpacing: 1,
                        }}
                      >
                        {k.toUpperCase().replace(/_/g, " ")}
                      </span>
                      <span
                        style={{
                          color:
                            String(v).includes("load") ||
                            String(v).includes("connect") ||
                            String(v).includes("run") ||
                            typeof v === "number"
                              ? "var(--qf-green)"
                              : "var(--qf-yellow)",
                        }}
                      >
                        {String(v).toUpperCase()}
                      </span>
                    </div>
                  ))}
                <div
                  style={{
                    color: "var(--qf-text-muted)",
                    fontSize: 10,
                    marginTop: 4,
                  }}
                >
                  v{health.version}
                </div>
              </div>
            )}
            <div style={{ display: "grid", gap: 10 }}>
              {[
                [
                  "API Docs",
                  `${import.meta.env.VITE_API_URL?.replace("/api", "") || "http://localhost:8000"}/api/docs`,
                ],
                [
                  "API ReDoc",
                  `${import.meta.env.VITE_API_URL?.replace("/api", "") || "http://localhost:8000"}/api/redoc`,
                ],
                ["Grafana", "http://localhost:3001"],
                ["Prometheus", "http://localhost:9090"],
              ].map(([l, url]) => (
                <div
                  key={l}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "var(--qf-bg-surface)",
                    borderRadius: 8,
                    padding: "10px 14px",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--qf-text-muted)",
                    }}
                  >
                    {l}
                  </span>
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--qf-cyan)",
                      textDecoration: "none",
                    }}
                  >
                    {url} ↗
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Save footer */}
        {tab !== "diagnostics" && (
          <div
            style={{
              marginTop: 24,
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: 14,
            }}
          >
            {saved && (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--qf-green)",
                }}
              >
                ✓ SETTINGS SAVED
              </span>
            )}
            <button className="qf-btn qf-btn-primary" onClick={save}>
              SAVE SETTINGS
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
