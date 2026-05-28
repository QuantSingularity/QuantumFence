import React, { createContext, useContext, useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Cameras from "./pages/Cameras";
import Alerts from "./pages/Alerts";
import DroneWatch from "./pages/DroneWatch";
import MapView from "./pages/MapView";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { WebSocketProvider } from "./context/WebSocketContext";

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <SplashScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function SplashScreen() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "var(--qf-bg-deep)",
        gap: 24,
      }}
    >
      <div style={{ position: "relative", width: 80, height: 80 }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: "2px solid transparent",
            borderTopColor: "var(--qf-cyan)",
            animation: "rotate-ring 1s linear infinite",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 8,
            borderRadius: "50%",
            border: "2px solid transparent",
            borderTopColor: "var(--qf-green)",
            animation: "rotate-ring 1.5s linear infinite reverse",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 16,
            borderRadius: "50%",
            background: "var(--qf-cyan-dim)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 20,
          }}
        >
          ⚡
        </div>
      </div>
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontSize: 18,
          color: "var(--qf-cyan)",
          letterSpacing: 4,
        }}
      >
        QUANTUMFENCE
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--qf-text-muted)",
        }}
      >
        INITIALIZING SYSTEMS...
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <Router>
          <div className="scan-overlay" />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <Layout>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/cameras" element={<Cameras />} />
                      <Route path="/alerts" element={<Alerts />} />
                      <Route path="/drones" element={<DroneWatch />} />
                      <Route path="/map" element={<MapView />} />
                      <Route path="/analytics" element={<Analytics />} />
                      <Route path="/settings" element={<Settings />} />
                    </Routes>
                  </Layout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </WebSocketProvider>
    </AuthProvider>
  );
}
