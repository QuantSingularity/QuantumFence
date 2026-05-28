import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";

const WsContext = createContext(null);

export function WebSocketProvider({ children }) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const listeners = useRef({});
  const [connected, setConnected] = useState(false);
  const [latestAlert, setLatestAlert] = useState(null);
  const [latestDetection, setLatestDetection] = useState(null);
  const [latestDrone, setLatestDrone] = useState(null);
  const [cameraStatuses, setCameraStatuses] = useState({});

  const emit = useCallback((event, data) => {
    (listeners.current[event] || []).forEach((cb) => cb(data));
  }, []);

  const connect = useCallback(() => {
    const token = localStorage.getItem("qf_token");
    if (!token) return; // not logged in yet

    const base = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
    const clientId = `web_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const url = `${base}/ws/${clientId}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        clearTimeout(reconnectTimer.current);
        // Keep-alive ping every 25 s
        ws._pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);
      };

      ws.onmessage = ({ data: raw }) => {
        let msg;
        try {
          msg = JSON.parse(raw);
        } catch {
          return;
        }
        const { type, data, camera_id, status } = msg;

        switch (type) {
          case "alert":
            setLatestAlert(data);
            emit("alert", data);
            break;
          case "detection":
            setLatestDetection(data);
            emit("detection", data);
            break;
          case "drone_detection":
            setLatestDrone(data);
            emit("drone_detection", data);
            break;
          case "camera_status":
            setCameraStatuses((prev) => ({
              ...prev,
              [String(camera_id)]: status,
            }));
            emit("camera_status", { camera_id, status });
            break;
          case "camera_added":
            emit("camera_added", msg);
            break;
          case "pong":
            break; // heartbeat reply, ignore
          default:
            emit(type, msg);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        clearInterval(ws._pingInterval);
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    } catch {
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, [emit]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearInterval(wsRef.current?._pingInterval);
      wsRef.current?.close();
    };
  }, [connect]);

  /** Subscribe to a named event. Returns an unsubscribe fn. */
  const on = useCallback((event, callback) => {
    if (!listeners.current[event]) listeners.current[event] = [];
    listeners.current[event].push(callback);
    return () => {
      listeners.current[event] = (listeners.current[event] || []).filter(
        (cb) => cb !== callback,
      );
    };
  }, []);

  /** Send a raw JSON message to the backend. */
  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  /** Ask backend to start processing a camera. */
  const startCamera = useCallback(
    (cameraId, streamUrl, config = {}) => {
      send({
        type: "start_camera",
        camera_id: cameraId,
        stream_url: streamUrl,
        config,
      });
    },
    [send],
  );

  return (
    <WsContext.Provider
      value={{
        connected,
        latestAlert,
        latestDetection,
        latestDrone,
        cameraStatuses,
        on,
        send,
        startCamera,
      }}
    >
      {children}
    </WsContext.Provider>
  );
}

export const useWebSocket = () => useContext(WsContext);
