import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  timeout: 15000,
});

// Attach token on every request
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("qf_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Handle 401 globally
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("qf_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

export default api;

// ── Camera API ───────────────────────────────────────────────────────────────
export const cameraApi = {
  list: (params) => api.get("/cameras", { params }),
  get: (id) => api.get(`/cameras/${id}`),
  create: (data) => api.post("/cameras", data),
  update: (id, d) => api.put(`/cameras/${id}`, d),
  delete: (id) => api.delete(`/cameras/${id}`),
  enable: (id) => api.post(`/cameras/${id}/enable`),
  disable: (id) => api.post(`/cameras/${id}/disable`),
  stats: (id) => api.get(`/cameras/${id}/stats`),
  // Returns image blob — call via fetch with auth header (see Cameras.jsx StatsModal)
  snapshotUrl: (id) => `${api.defaults.baseURL}/cameras/${id}/snapshot`,
};

// ── Alert API ────────────────────────────────────────────────────────────────
export const alertApi = {
  list: (params) => api.get("/alerts", { params }),
  get: (id) => api.get(`/alerts/${id}`),
  stats: () => api.get("/alerts/stats"),
  acknowledge: (id) => api.post(`/alerts/${id}/acknowledge`),
  resolve: (id) => api.post(`/alerts/${id}/resolve`),
  update: (id, d) => api.put(`/alerts/${id}`, d),
  delete: (id) => api.delete(`/alerts/${id}`),
};

// ── Drone API ────────────────────────────────────────────────────────────────
export const droneApi = {
  list: (params) => api.get("/drones", { params }),
  active: () => api.get("/drones/active"),
  stats: () => api.get("/drones/stats"),
};

// ── Analytics API ────────────────────────────────────────────────────────────
export const analyticsApi = {
  overview: () => api.get("/analytics/overview"),
  detectionsTimeline: (days) =>
    api.get("/analytics/detections/timeline", { params: { days } }),
  alertsByType: (days) =>
    api.get("/analytics/alerts/by-type", { params: { days } }),
  heatmap: () => api.get("/analytics/heatmap"),
  cameraPerformance: () => api.get("/analytics/cameras/performance"),
};

// ── Geofence API ─────────────────────────────────────────────────────────────
export const geofenceApi = {
  list: () => api.get("/geofences"),
  get: (id) => api.get(`/geofences/${id}`),
  create: (data) => api.post("/geofences", data),
  update: (id, d) => api.put(`/geofences/${id}`, d),
  delete: (id) => api.delete(`/geofences/${id}`),
  checkPoint: (id, lat, lng) =>
    api.post(`/geofences/${id}/check-point`, null, { params: { lat, lng } }),
};

// ── Auth API ─────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) => {
    const form = new FormData();
    form.append("username", username);
    form.append("password", password);
    return api.post("/auth/login", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  me: () => api.get("/auth/me"),
  refresh: (token) =>
    api.post("/auth/refresh", null, { params: { refresh_token: token } }),
};

// ── System API ───────────────────────────────────────────────────────────────
export const systemApi = {
  health: () =>
    axios.get(
      (import.meta.env.VITE_API_URL || "http://localhost:8000/api").replace(
        "/api",
        "",
      ) + "/health",
    ),
};
