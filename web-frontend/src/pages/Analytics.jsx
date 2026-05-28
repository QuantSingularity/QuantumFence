import React, { useState, useEffect, useCallback } from "react";
import { analyticsApi } from "../services/api";

// ── Simple Bar Chart ──────────────────────────────────────────────────────────
function BarChart({
  data = [],
  keyField,
  valueField,
  color = "var(--qf-cyan)",
  label = "",
  height = 130,
}) {
  if (!data.length)
    return (
      <div
        style={{
          textAlign: "center",
          padding: 40,
          color: "var(--qf-text-muted)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
        }}
      >
        NO DATA
      </div>
    );
  const max = Math.max(...data.map((d) => d[valueField] || 0), 1);
  return (
    <div>
      {label && (
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            letterSpacing: 2,
            marginBottom: 14,
          }}
        >
          {label}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height }}>
        {data.map((d, i) => {
          const val = d[valueField] || 0;
          const pct = (val / max) * 100;
          const key = d[keyField] || i;
          return (
            <div
              key={i}
              title={`${key}: ${val}`}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
                height: "100%",
                justifyContent: "flex-end",
              }}
            >
              <div
                style={{
                  width: "100%",
                  height: `${Math.max(pct, val > 0 ? 3 : 0)}%`,
                  background: color,
                  borderRadius: "3px 3px 0 0",
                  opacity: 0.85,
                  transition: "height 0.6s ease",
                  minHeight: val > 0 ? 3 : 0,
                }}
              />
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 8,
                  color: "var(--qf-text-muted)",
                  transform: "rotate(-45deg)",
                  whiteSpace: "nowrap",
                  transformOrigin: "center top",
                  marginBottom: 2,
                }}
              >
                {String(key).slice(-5)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Camera Performance Bar ────────────────────────────────────────────────────
function PerfBar({ value, max, color = "var(--qf-cyan)" }) {
  const pct = Math.min((value / Math.max(max, 1)) * 100, 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        style={{
          flex: 1,
          height: 5,
          background: "var(--qf-bg-surface)",
          borderRadius: 3,
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 3,
            transition: "width 0.6s ease",
          }}
        />
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color,
          minWidth: 28,
          textAlign: "right",
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function Analytics() {
  const [overview, setOverview] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [byType, setByType] = useState([]);
  const [performance, setPerformance] = useState([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, tl, bt, perf] = await Promise.all([
        analyticsApi.overview(),
        analyticsApi.detectionsTimeline(days),
        analyticsApi.alertsByType(days),
        analyticsApi.cameraPerformance(),
      ]);
      setOverview(ov.data);
      setTimeline(tl.data);
      setByType(bt.data);
      setPerformance(perf.data);
    } catch (e) {
      console.error("Analytics load error:", e);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const maxDet = Math.max(...performance.map((p) => p.detections || 0), 1);
  const maxAlt = Math.max(...performance.map((p) => p.alerts || 0), 1);

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
            INTELLIGENCE ANALYTICS
          </h1>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 4,
            }}
          >
            Threat trends, detection patterns, and camera performance
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <select
            className="qf-select"
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
          >
            {[7, 14, 30].map((d) => (
              <option key={d} value={d}>
                LAST {d} DAYS
              </option>
            ))}
          </select>
          <button
            className="qf-btn qf-btn-outline"
            style={{ fontSize: 12 }}
            onClick={load}
          >
            ↻
          </button>
        </div>
      </div>

      {/* ── Summary row ────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: 14,
          marginBottom: 24,
        }}
      >
        {[
          ["CAMERAS", overview?.cameras?.total ?? "—", "var(--qf-cyan)"],
          ["ONLINE", overview?.cameras?.online ?? "—", "var(--qf-green)"],
          ["24H ALERTS", overview?.alerts_24h ?? "—", "var(--qf-orange)"],
          [
            "DRONE HITS",
            overview?.drone_detections_24h ?? "—",
            "var(--qf-yellow)",
          ],
          [
            "SYSTEM HEALTH",
            overview ? `${overview.system_health}%` : "—",
            "var(--qf-green)",
          ],
        ].map(([l, v, c]) => (
          <div
            key={l}
            className="qf-card"
            style={{ textAlign: "center", padding: "16px 12px" }}
          >
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 24,
                color: c,
                marginBottom: 6,
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

      {/* ── Charts row ─────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div className="qf-card">
          {loading ? (
            <div
              style={{
                textAlign: "center",
                padding: 40,
                color: "var(--qf-text-muted)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              LOADING CHART…
            </div>
          ) : (
            <BarChart
              data={timeline}
              keyField="date"
              valueField="detections"
              color="var(--qf-cyan)"
              label={`DETECTION ACTIVITY — LAST ${days} DAYS`}
            />
          )}
        </div>
        <div className="qf-card">
          {loading ? (
            <div
              style={{
                textAlign: "center",
                padding: 40,
                color: "var(--qf-text-muted)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              LOADING CHART…
            </div>
          ) : (
            <BarChart
              data={byType}
              keyField="type"
              valueField="count"
              color="var(--qf-orange)"
              label={`ALERTS BY DETECTION TYPE — LAST ${days} DAYS`}
            />
          )}
        </div>
      </div>

      {/* ── Camera performance table ───────────────────────────────────────── */}
      <div className="qf-card" style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: "14px 20px",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            letterSpacing: 2,
            borderBottom: "1px solid var(--qf-border)",
          }}
        >
          CAMERA PERFORMANCE
        </div>
        <table className="qf-table">
          <thead>
            <tr>
              <th>CAMERA</th>
              <th>STATUS</th>
              <th style={{ width: 200 }}>DETECTIONS</th>
              <th style={{ width: 200 }}>ALERTS</th>
            </tr>
          </thead>
          <tbody>
            {performance.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  style={{
                    textAlign: "center",
                    padding: 40,
                    color: "var(--qf-text-muted)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  NO CAMERA DATA
                </td>
              </tr>
            ) : (
              performance.map((p) => (
                <tr key={p.camera_id}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 7 }}
                    >
                      <span
                        className={`status-dot ${p.status === "online" ? "status-online" : "status-offline"}`}
                      />
                      <span
                        style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}
                      >
                        {p.status?.toUpperCase()}
                      </span>
                    </div>
                  </td>
                  <td>
                    <PerfBar
                      value={p.detections}
                      max={maxDet}
                      color="var(--qf-cyan)"
                    />
                  </td>
                  <td>
                    <PerfBar
                      value={p.alerts}
                      max={maxAlt}
                      color="var(--qf-orange)"
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
