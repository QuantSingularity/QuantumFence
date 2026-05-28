import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--qf-bg-deep)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
      className="qf-grid-bg"
    >
      {/* Background glow orbs */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          top: -200,
          left: -200,
          background:
            "radial-gradient(circle, var(--qf-cyan-glow) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 400,
          height: 400,
          borderRadius: "50%",
          bottom: -100,
          right: -100,
          background: "radial-gradient(circle, #00ff8811 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          width: "100%",
          maxWidth: 420,
          padding: 24,
          position: "relative",
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 72,
              height: 72,
              borderRadius: 20,
              background:
                "linear-gradient(135deg, var(--qf-cyan-dim), var(--qf-bg-surface))",
              border: "1px solid var(--qf-cyan)",
              fontSize: 32,
              marginBottom: 20,
              boxShadow: "0 0 40px var(--qf-cyan-dim)",
            }}
          >
            ⚡
          </div>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 28,
              fontWeight: 900,
              color: "var(--qf-cyan)",
              letterSpacing: 6,
              textShadow: "0 0 30px var(--qf-cyan)",
              marginBottom: 8,
            }}
          >
            QUANTUMFENCE
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              letterSpacing: 3,
            }}
          >
            PERIMETER DEFENSE AI SYSTEM
          </div>
        </div>

        {/* Login Card */}
        <div
          className="qf-card"
          style={{
            background: "var(--qf-bg-card)",
            border: "1px solid var(--qf-border)",
            boxShadow: "0 0 60px var(--qf-cyan-glow)",
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              letterSpacing: 2,
              marginBottom: 24,
              textAlign: "center",
            }}
          >
            OPERATOR AUTHENTICATION
          </div>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label
                style={{
                  display: "block",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  marginBottom: 6,
                }}
              >
                USERNAME
              </label>
              <input
                className="qf-input"
                type="text"
                autoComplete="username"
                placeholder="Enter username"
                value={form.username}
                onChange={(e) =>
                  setForm((f) => ({ ...f, username: e.target.value }))
                }
                required
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label
                style={{
                  display: "block",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--qf-text-muted)",
                  letterSpacing: 1,
                  marginBottom: 6,
                }}
              >
                PASSWORD
              </label>
              <input
                className="qf-input"
                type="password"
                autoComplete="current-password"
                placeholder="Enter password"
                value={form.password}
                onChange={(e) =>
                  setForm((f) => ({ ...f, password: e.target.value }))
                }
                required
              />
            </div>

            {error && (
              <div
                style={{
                  background: "var(--qf-red-dim)",
                  border: "1px solid var(--qf-red)",
                  borderRadius: 8,
                  padding: "10px 14px",
                  marginBottom: 16,
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--qf-red)",
                }}
              >
                ⚠ {error}
              </div>
            )}

            <button
              type="submit"
              className="qf-btn qf-btn-primary"
              style={{
                width: "100%",
                justifyContent: "center",
                fontSize: 13,
                padding: "13px",
              }}
              disabled={loading}
            >
              {loading ? (
                <span
                  style={{ display: "flex", alignItems: "center", gap: 10 }}
                >
                  <span
                    style={{
                      width: 14,
                      height: 14,
                      border: "2px solid transparent",
                      borderTopColor: "var(--qf-bg-deep)",
                      borderRadius: "50%",
                      animation: "rotate-ring 0.8s linear infinite",
                      display: "inline-block",
                    }}
                  />
                  AUTHENTICATING...
                </span>
              ) : (
                "ACCESS SYSTEM"
              )}
            </button>
          </form>

          {/* Default credentials hint */}
          <div
            style={{
              marginTop: 20,
              padding: "10px 14px",
              background: "var(--qf-bg-surface)",
              borderRadius: 8,
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--qf-text-muted)",
              lineHeight: 1.7,
            }}
          >
            DEFAULT CREDENTIALS (change after first login)
            <br />
            USERNAME: <span style={{ color: "var(--qf-cyan)" }}>
              admin
            </span>{" "}
            &nbsp; PASSWORD:{" "}
            <span style={{ color: "var(--qf-cyan)" }}>quantumfence</span>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            textAlign: "center",
            marginTop: 24,
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--qf-text-muted)",
            letterSpacing: 1,
            lineHeight: 1.8,
          }}
        >
          QUANTUMFENCE v1.0.0 &nbsp;·&nbsp; QUANTUM-ACCELERATED PERIMETER
          DEFENSE
          <br />
          ALL ACCESS ATTEMPTS ARE LOGGED AND MONITORED
        </div>
      </div>
    </div>
  );
}
