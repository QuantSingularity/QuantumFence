import React, { createContext, useContext, useState, useEffect } from "react";
import { authApi } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount — try to restore session from stored token
  useEffect(() => {
    const token = localStorage.getItem("qf_token");
    if (!token) {
      setLoading(false);
      return;
    }

    authApi
      .me()
      .then((r) => setUser(r.data))
      .catch(() => {
        localStorage.removeItem("qf_token");
        localStorage.removeItem("qf_refresh");
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (username, password) => {
    const r = await authApi.login(username, password);
    const { access_token, refresh_token, user: userData } = r.data;
    localStorage.setItem("qf_token", access_token);
    localStorage.setItem("qf_refresh", refresh_token);
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem("qf_token");
    localStorage.removeItem("qf_refresh");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
