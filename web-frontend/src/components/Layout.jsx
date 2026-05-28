import React, { useState, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useWebSocket } from "../context/WebSocketContext";

const NAV = [
  { path: "/", icon: "⬡", label: "DASHBOARD" },
  { path: "/cameras", icon: "◉", label: "CAMERAS" },
  { path: "/alerts", icon: "⚠", label: "ALERTS" },
  { path: "/drones", icon: "◈", label: "DRONE WATCH" },
  { path: "/map", icon: "⊕", label: "MAP VIEW" },
  { path: "/analytics", icon: "▣", label: "ANALYTICS" },
  { path: "/settings", icon: "⊙", label: "SETTINGS" },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { connected, latestAlert, latestDrone } = useWebSocket();
  const location = useLocation();
  const navigate = useNavigate();
  const [alertFlash, setAlertFlash] = useState(false);
  const [droneFlash, setDroneFlash] = useState(false);
  const [unreadAlerts, setUnreadAlerts] = useState(0);

  // Flash red on new alert
  useEffect(() => {
    if (!latestAlert) return;
    setAlertFlash(true);
    setUnreadAlerts((n) => n + 1);
    const t = setTimeout(() => setAlertFlash(false), 3000);
    return () => clearTimeout(t);
  }, [latestAlert]);

  // Flash yellow on drone detection
  useEffect(() => {
    if (!latestDrone) return;
    setDroneFlash(true);
    const t = setTimeout(() => setDroneFlash(false), 3000);
    return () => clearTimeout(t);
  }, [latestDrone]);

  // Clear unread count when user navigates to alerts
  useEffect(() => {
    if (location.pathname === "/alerts") setUnreadAlerts(0);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        style={{
          width: 224,
          background: "var(--qf-bg-dark)",
          borderRight: "1px solid var(--qf-border)",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
          position: "relative",
          overflow: "hidden",
          userSelect: "none",
        }}
      >
        {/* Vertical glow accent */}
        <div
          style={{
            position: "absolute",
            right: 0,
            top: 0,
            bottom: 0,
            width: 1,
            background:
              "linear-gradient(to bottom, transparent, var(--qf-cyan), transparent)",
            opacity: 0.25,
            pointerEvents: "none",
          }}
        />

        {/* ── Logo ───────────────────────────────────────────────────────────── */}
        <div
          style={{
            padding: "26px 20px 22px",
            borderBottom: "1px solid var(--qf-border)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                flexShrink: 0,
                background:
                  "linear-gradient(135deg, var(--qf-cyan-dim), var(--qf-bg-surface))",
                border: "1px solid var(--qf-cyan)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 18,
                boxShadow: "0 0 16px var(--qf-cyan-dim)",
              }}
            >
              ⚡
            </div>
            <div>
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: 15,
                  fontWeight: 900,
                  color: "var(--qf-cyan)",
                  letterSpacing: 3,
                  textShadow: "0 0 20px var(--qf-cyan)",
                  lineHeight: 1.2,
                }}
              >
                QUANTUM
                <br />
                FENCE
              </div>
            </div>
          </div>
          <div
            style={{
              marginTop: 10,
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--qf-text-muted)",
              letterSpacing: 2,
            }}
          >
            PERIMETER DEFENSE AI v1.0
          </div>
        </div>

        {/* ── Live status pill ───────────────────────────────────────────────── */}
        <div
          style={{
            margin: "10px 12px",
            padding: "7px 12px",
            background: connected
              ? "var(--qf-green-dim)"
              : "var(--qf-bg-surface)",
            border: `1px solid ${connected ? "var(--qf-green)" : "var(--qf-border)"}`,
            borderRadius: 20,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span
            className={`status-dot ${connected ? "status-online" : "status-offline"}`}
          />
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: connected ? "var(--qf-green)" : "var(--qf-text-muted)",
              letterSpacing: 1,
            }}
          >
            {connected ? "LIVE FEED ACTIVE" : "RECONNECTING…"}
          </span>
        </div>

        {/* ── Navigation ─────────────────────────────────────────────────────── */}
        <nav style={{ flex: 1, overflowY: "auto", paddingTop: 4 }}>
          {NAV.map(({ path, icon, label }) => {
            const isActive =
              path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(path);
            const isAlert = path === "/alerts" && alertFlash;
            const isDrone = path === "/drones" && droneFlash;
            const hasUnread = path === "/alerts" && unreadAlerts > 0;

            return (
              <NavLink
                key={path}
                to={path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 20px",
                  textDecoration: "none",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: 1.5,
                  fontWeight: 600,
                  color: isActive
                    ? "var(--qf-cyan)"
                    : isAlert
                      ? "var(--qf-red)"
                      : isDrone
                        ? "var(--qf-yellow)"
                        : "var(--qf-text-muted)",
                  background: isActive
                    ? "var(--qf-cyan-glow)"
                    : isAlert
                      ? "var(--qf-red-dim)"
                      : "transparent",
                  borderLeft: `3px solid ${isActive ? "var(--qf-cyan)" : isAlert ? "var(--qf-red)" : "transparent"}`,
                  transition: "all 0.18s",
                }}
              >
                <span
                  style={{ fontSize: 15, minWidth: 20, textAlign: "center" }}
                >
                  {icon}
                </span>
                <span style={{ flex: 1 }}>{label}</span>

                {/* Unread badge */}
                {hasUnread && (
                  <span
                    style={{
                      background: "var(--qf-red)",
                      color: "white",
                      borderRadius: 10,
                      fontSize: 9,
                      fontWeight: 900,
                      padding: "2px 6px",
                      letterSpacing: 0,
                      animation: "pulse-red 1s infinite",
                    }}
                  >
                    {unreadAlerts > 9 ? "9+" : unreadAlerts}
                  </span>
                )}

                {/* Drone flash dot */}
                {isDrone && !isActive && (
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: "var(--qf-yellow)",
                      animation: "pulse-red 0.6s infinite",
                    }}
                  />
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* ── User strip ─────────────────────────────────────────────────────── */}
        <div
          style={{
            padding: "14px 16px",
            borderTop: "1px solid var(--qf-border)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              flexShrink: 0,
              background: "var(--qf-bg-surface)",
              border: "1px solid var(--qf-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              color: "var(--qf-cyan)",
              fontWeight: 700,
              fontFamily: "var(--font-display)",
            }}
          >
            {user?.username?.[0]?.toUpperCase() || "U"}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user?.full_name || user?.username}
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--qf-text-muted)",
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "var(--font-mono)",
              }}
            >
              {user?.role}
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Logout"
            style={{
              background: "none",
              border: "none",
              color: "var(--qf-text-muted)",
              cursor: "pointer",
              fontSize: 17,
              padding: 4,
              lineHeight: 1,
              transition: "color 0.2s",
            }}
            onMouseEnter={(e) => (e.target.style.color = "var(--qf-red)")}
            onMouseLeave={(e) =>
              (e.target.style.color = "var(--qf-text-muted)")
            }
          >
            ⏻
          </button>
        </div>
      </aside>

      {/* ── Main content area ─────────────────────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          overflow: "auto",
          background: "var(--qf-bg-deep)",
          display: "flex",
          flexDirection: "column",
        }}
        className="qf-grid-bg"
      >
        {children}
      </main>
    </div>
  );
}
