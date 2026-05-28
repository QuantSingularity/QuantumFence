import React, { useState, useEffect, useCallback, useRef } from "react";
import { cameraApi, geofenceApi, alertApi } from "../services/api";
import { useWebSocket } from "../context/WebSocketContext";

export default function MapView() {
  const [cameras, setCameras] = useState([]);
  const [geofences, setGeofences] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mapReady, setMapReady] = useState(false);

  const mapRef = useRef(null);
  const leafletMap = useRef(null);
  const markersRef = useRef([]);
  const geofenceLayersRef = useRef([]);

  const { latestAlert, latestDrone, latestDetection } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const [c, g, a] = await Promise.all([
        cameraApi.list(),
        geofenceApi.list(),
        alertApi.list({ status: "active", limit: 50 }),
      ]);
      setCameras(c.data);
      setGeofences(g.data);
      setAlerts(a.data);
    } catch (e) {
      console.error("MapView load error:", e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Reload alerts when live events arrive
  useEffect(() => {
    if (latestAlert || latestDrone) load();
  }, [latestAlert, latestDrone, load]);

  // Load Leaflet from CDN
  useEffect(() => {
    if (document.getElementById("leaflet-css")) {
      setMapReady(true);
      return;
    }

    const link = document.createElement("link");
    link.id = "leaflet-css";
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => setMapReady(true);
    document.head.appendChild(script);

    return () => {
      // Leave them in DOM — cheaper than reloading
    };
  }, []);

  // Initialise map once
  useEffect(() => {
    if (!mapReady || !mapRef.current || leafletMap.current) return;
    const L = window.L;
    const map = L.map(mapRef.current, {
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "© CARTO | QuantumFence", maxZoom: 19 },
    ).addTo(map);

    map.setView([33.6844, 73.0479], 16);
    leafletMap.current = map;
  }, [mapReady]);

  // Re-draw markers/geofences whenever data changes
  useEffect(() => {
    if (!leafletMap.current || !window.L) return;
    const L = window.L;
    const map = leafletMap.current;

    // Clear
    markersRef.current.forEach((m) => map.removeLayer(m));
    markersRef.current = [];
    geofenceLayersRef.current.forEach((l) => map.removeLayer(l));
    geofenceLayersRef.current = [];

    // Camera markers
    cameras.forEach((cam) => {
      if (!cam.latitude || !cam.longitude) return;
      const isOnline = cam.status === "online";
      const icon = L.divIcon({
        html: `
          <div style="
            width:30px;height:30px;border-radius:50%;
            background:${isOnline ? "#00ff8830" : "#1a3a5c"};
            border:2px solid ${isOnline ? "#00ff88" : "#3d5a72"};
            display:flex;align-items:center;justify-content:center;
            font-size:13px;
            box-shadow:${isOnline ? "0 0 14px #00ff88" : "none"};
            cursor:pointer;
          ">◉</div>`,
        className: "",
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      });
      const marker = L.marker([cam.latitude, cam.longitude], { icon })
        .addTo(map)
        .bindPopup(
          `
          <div style="font-family:monospace;background:#0a1628;color:#e8f4f8;padding:14px;border-radius:10px;min-width:220px;border:1px solid #1a3a5c">
            <div style="color:#00d4ff;font-weight:900;font-size:14px;margin-bottom:10px">${cam.name}</div>
            <div style="font-size:12px;line-height:1.8">
              <b>Status:</b> <span style="color:${isOnline ? "#00ff88" : "#7a9bb5"}">${cam.status?.toUpperCase()}</span><br/>
              <b>Type:</b> ${cam.camera_type?.toUpperCase()}<br/>
              <b>Location:</b> ${cam.location_name || "N/A"}<br/>
              <b>Direction:</b> ${cam.direction_degrees}° &nbsp; <b>FOV:</b> ${cam.fov_degrees}°<br/>
              <b>Res:</b> ${cam.resolution_width}×${cam.resolution_height} @ ${cam.fps}fps
            </div>
          </div>
        `,
          { className: "qf-popup" },
        );
      marker.on("click", () => setSelected(cam));
      markersRef.current.push(marker);
    });

    // Alert markers
    alerts.forEach((alert) => {
      if (!alert.latitude || !alert.longitude) return;
      const sevColor = {
        critical: "#ff2d55",
        high: "#ff6b35",
        medium: "#ffd60a",
        low: "#00ff88",
      };
      const col = sevColor[alert.severity] || "#ff6b35";
      const icon = L.divIcon({
        html: `<div style="
          width:22px;height:22px;border-radius:50%;
          background:${col}33;border:2px solid ${col};
          display:flex;align-items:center;justify-content:center;
          font-size:10px;color:${col};
        ">⚠</div>`,
        className: "",
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      const m = L.marker([alert.latitude, alert.longitude], { icon })
        .addTo(map)
        .bindPopup(
          `
          <div style="font-family:monospace;background:#0a1628;padding:12px;border-radius:8px;color:#e8f4f8;border:1px solid ${col}">
            <b style="color:${col}">${alert.alert_type?.replace(/_/g, " ").toUpperCase()}</b><br/>
            ${alert.title}<br/>
            <small style="color:#7a9bb5">${new Date(alert.created_at).toLocaleString()}</small>
          </div>
        `,
          { className: "qf-popup" },
        );
      markersRef.current.push(m);
    });

    // Geofence polygons
    geofences.forEach((gf) => {
      if (!gf.coordinates?.length || !gf.is_active) return;
      const col = gf.color || "#FF4444";
      const latlngs = gf.coordinates.map(([lng, lat]) => [lat, lng]);
      const polygon = L.polygon(latlngs, {
        color: col,
        fillColor: col,
        fillOpacity: 0.08,
        weight: 2,
        dashArray: "8 4",
      }).addTo(map).bindPopup(`
        <div style="font-family:monospace;background:#0a1628;padding:12px;border-radius:8px;color:#e8f4f8">
          <b style="color:#00d4ff">${gf.name}</b><br/>
          ${gf.description || ""}<br/>
          <small style="color:#7a9bb5">Buffer: ${gf.buffer_meters}m</small>
        </div>
      `);
      geofenceLayersRef.current.push(polygon);
    });

    // Fit map bounds to cameras
    const withCoords = cameras.filter((c) => c.latitude && c.longitude);
    if (withCoords.length > 0) {
      const bounds = L.latLngBounds(
        withCoords.map((c) => [c.latitude, c.longitude]),
      );
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 17 });
    }
  }, [cameras, geofences, alerts, mapReady]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div
        style={{
          padding: "18px 28px",
          borderBottom: "1px solid var(--qf-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
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
            TACTICAL MAP
          </h1>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--qf-text-muted)",
              marginTop: 3,
            }}
          >
            {cameras.length} cameras &nbsp;·&nbsp; {geofences.length} zones
            &nbsp;·&nbsp; {alerts.length} active alerts
          </div>
        </div>
        <div
          style={{
            display: "flex",
            gap: 20,
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--qf-text-muted)",
          }}
        >
          <span>◉ CAMERA</span>
          <span style={{ color: "var(--qf-red)" }}>⚠ ALERT</span>
          <span
            style={{
              color: "var(--qf-cyan)",
              borderBottom: "1px dashed var(--qf-cyan)",
            }}
          >
            — GEOFENCE
          </span>
        </div>
      </div>

      {/* ── Map ─────────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: "relative" }}>
        <div ref={mapRef} style={{ width: "100%", height: "100%" }} />

        {!mapReady && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--qf-bg-dark)",
              flexDirection: "column",
              gap: 16,
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-display)",
                color: "var(--qf-cyan)",
                fontSize: 16,
                letterSpacing: 3,
              }}
            >
              LOADING MAP…
            </div>
          </div>
        )}

        {/* Selected camera panel */}
        {selected && (
          <div
            style={{
              position: "absolute",
              top: 16,
              right: 16,
              width: 280,
              background: "var(--qf-bg-card)",
              border: "1px solid var(--qf-cyan)",
              borderRadius: 14,
              padding: 18,
              zIndex: 1000,
              animation: "slide-in-right 0.2s ease",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: 12,
                  color: "var(--qf-cyan)",
                  letterSpacing: 2,
                }}
              >
                CAMERA DETAIL
              </div>
              <button
                onClick={() => setSelected(null)}
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
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>
              {selected.name}
            </div>
            {[
              ["Status", selected.status?.toUpperCase()],
              ["Location", selected.location_name],
              ["Type", selected.camera_type?.toUpperCase()],
              ["Direction", `${selected.direction_degrees}°`],
              ["FOV", `${selected.fov_degrees}°`],
              [
                "Res",
                `${selected.resolution_width}×${selected.resolution_height}`,
              ],
              [
                "Coords",
                selected.latitude
                  ? `${selected.latitude.toFixed(4)}, ${selected.longitude.toFixed(4)}`
                  : null,
              ],
            ]
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 7,
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      color: "var(--qf-text-muted)",
                    }}
                  >
                    {k}
                  </span>
                  <span
                    style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              {selected.detect_persons && (
                <span className="badge badge-low" style={{ fontSize: 9 }}>
                  PERSON
                </span>
              )}
              {selected.detect_vehicles && (
                <span className="badge badge-medium" style={{ fontSize: 9 }}>
                  VEHICLE
                </span>
              )}
              {selected.detect_drones && (
                <span className="badge badge-high" style={{ fontSize: 9 }}>
                  DRONE
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
