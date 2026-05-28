import React, { useState, useEffect, useCallback } from "react";
import { alertApi } from "../services/api";
import { useWebSocket } from "../context/WebSocketContext";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState({ status: "", severity: "", hours: 24 });
  const [loading, setLoading] = useState(true);
  const { latestAlert } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const params = { limit: 100 };
      if (filter.status) params.status = filter.status;
      if (filter.severity) params.severity = filter.severity;
      params.hours = filter.hours;
      const [al, st] = await Promise.all([
        alertApi.list(params),
        alertApi.stats(),
      ]);
      setAlerts(al.data);
      setStats(st.data);
    } catch (e) {
      console.error("Alerts load error:", e);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);
  // Reload when a new live alert arrives
  useEffect(() => {
    if (latestAlert) load();
  }, [latestAlert, load]);

  const handleAck = async (id) => {
    await alertApi.acknowledge(id);
    load();
  };
  const handleResolve = async (id) => {
    await alertApi.resolve(id);
    load();
  };

  const sevColors = {
    critical: "var(--sev-critical)",
    high: "var(--sev-high)",
    medium: "var(--sev-medium)",
    low: "var(--sev-low)",
  };

  return (
    <div style={{ padding: 28 }}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
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
            ALERT MANAGEMENT
          </h1>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 4,
            }}
          >
            {stats?.active ?? 0} active · {stats?.total ?? 0} total
          </div>
        </div>

        {/* Summary badges */}
        {stats && (
          <div style={{ display: "flex", gap: 10 }}>
            {[
              ["CRITICAL", stats.critical, "var(--sev-critical)"],
              ["HIGH", stats.high, "var(--sev-high)"],
              ["MEDIUM", stats.medium, "var(--sev-medium)"],
              ["ACTIVE", stats.active, "var(--qf-cyan)"],
            ].map(([l, v, c]) => (
              <div
                key={l}
                style={{
                  background: "var(--qf-bg-card)",
                  border: "1px solid var(--qf-border)",
                  borderRadius: 10,
                  padding: "8px 16px",
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: 22,
                    color: c,
                  }}
                >
                  {v}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    color: "var(--qf-text-muted)",
                    letterSpacing: 1,
                  }}
                >
                  {l}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Filters ──────────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <select
          className="qf-select"
          value={filter.status}
          onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
        >
          {["", "active", "acknowledged", "resolved", "false_positive"].map(
            (o) => (
              <option key={o} value={o}>
                {o ? o.replace(/_/g, " ").toUpperCase() : "ALL STATUSES"}
              </option>
            ),
          )}
        </select>
        <select
          className="qf-select"
          value={filter.severity}
          onChange={(e) =>
            setFilter((f) => ({ ...f, severity: e.target.value }))
          }
        >
          {["", "critical", "high", "medium", "low"].map((o) => (
            <option key={o} value={o}>
              {o ? o.toUpperCase() : "ALL SEVERITIES"}
            </option>
          ))}
        </select>
        <select
          className="qf-select"
          value={filter.hours}
          onChange={(e) =>
            setFilter((f) => ({ ...f, hours: parseInt(e.target.value) }))
          }
        >
          {[6, 12, 24, 48, 168].map((h) => (
            <option key={h} value={h}>
              LAST {h}H
            </option>
          ))}
        </select>
        <button
          className="qf-btn qf-btn-outline"
          onClick={load}
          style={{ fontSize: 12 }}
        >
          ↻ REFRESH
        </button>
      </div>

      {/* ── Table ─────────────────────────────────────────────────────────────── */}
      <div className="qf-card" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 50,
              color: "var(--qf-text-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            LOADING ALERTS...
          </div>
        ) : (
          <table className="qf-table">
            <thead>
              <tr>
                <th>SEV</th>
                <th>TYPE</th>
                <th>TITLE / AI SUMMARY</th>
                <th>CAMERA</th>
                <th>SNAPSHOT</th>
                <th>TIME</th>
                <th>STATUS</th>
                <th>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    style={{
                      textAlign: "center",
                      padding: 48,
                      color: "var(--qf-text-muted)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    ✓ NO ALERTS FOUND
                  </td>
                </tr>
              ) : (
                alerts.map((a) => (
                  <tr key={a.id} style={{ animation: "fade-in-up 0.2s ease" }}>
                    <td>
                      <span className={`badge badge-${a.severity}`}>
                        {a.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--qf-text-secondary)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {a.alert_type?.replace(/_/g, " ").toUpperCase()}
                    </td>
                    <td style={{ maxWidth: 280 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: 13,
                          marginBottom: 3,
                        }}
                      >
                        {a.title}
                      </div>
                      {a.ai_summary && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--qf-text-muted)",
                            lineHeight: 1.4,
                          }}
                        >
                          🤖 {a.ai_summary.slice(0, 100)}
                          {a.ai_summary.length > 100 ? "…" : ""}
                        </div>
                      )}
                      {a.recommended_action && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--qf-green)",
                            marginTop: 3,
                          }}
                        >
                          ⚡ {a.recommended_action.slice(0, 80)}
                          {a.recommended_action.length > 80 ? "…" : ""}
                        </div>
                      )}
                    </td>
                    <td
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 12,
                        whiteSpace: "nowrap",
                      }}
                    >
                      CAM {String(a.camera_id).padStart(2, "0")}
                    </td>
                    <td>
                      {a.snapshot_path ? (
                        <img
                          src={`/snapshots/${a.snapshot_path.split("/").pop()}`}
                          alt="snapshot"
                          style={{
                            width: 64,
                            height: 40,
                            objectFit: "cover",
                            borderRadius: 4,
                            border: "1px solid var(--qf-border)",
                          }}
                          onError={(e) => {
                            e.target.style.display = "none";
                          }}
                        />
                      ) : (
                        <span
                          style={{
                            color: "var(--qf-text-muted)",
                            fontSize: 11,
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          —
                        </span>
                      )}
                    </td>
                    <td
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--qf-text-muted)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td>
                      <span
                        className={`badge badge-${
                          a.status === "active"
                            ? "high"
                            : a.status === "acknowledged"
                              ? "medium"
                              : "low"
                        }`}
                      >
                        {a.status?.replace(/_/g, " ").toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          gap: 6,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {a.status === "active" && (
                          <button
                            className="qf-btn qf-btn-outline"
                            style={{ fontSize: 10, padding: "5px 10px" }}
                            onClick={() => handleAck(a.id)}
                          >
                            ACK
                          </button>
                        )}
                        {a.status !== "resolved" && (
                          <button
                            className="qf-btn qf-btn-primary"
                            style={{ fontSize: 10, padding: "5px 10px" }}
                            onClick={() => handleResolve(a.id)}
                          >
                            RESOLVE
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
