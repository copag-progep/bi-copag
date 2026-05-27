import { createContext, useContext, useEffect, useState } from "react";

import api from "../api/client";
import { clearAnalyticsCache } from "../hooks/useAnalyticsData";


const AuthContext = createContext(null);


export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("sei-bi-token"));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("sei-bi-user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(() => Boolean(token && !user));

  useEffect(() => {
    async function restoreSession() {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
        localStorage.setItem("sei-bi-user", JSON.stringify(data));
      } catch {
        // Sessão inválida — limpa cache para evitar que dados do usuário anterior sejam exibidos
        clearAnalyticsCache();
        localStorage.removeItem("sei-bi-token");
        localStorage.removeItem("sei-bi-user");
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    restoreSession();
  }, [token]);

  async function login(credentials) {
    // Limpa cache antes do login para evitar contaminação entre sessões de usuários diferentes
    clearAnalyticsCache();
    const { data } = await api.post("/auth/login", credentials);
    localStorage.setItem("sei-bi-token", data.access_token);
    localStorage.setItem("sei-bi-user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }

  function logout() {
    // Limpa cache ao sair para não vazar dados do usuário para a próxima sessão
    clearAnalyticsCache();
    localStorage.removeItem("sei-bi-token");
    localStorage.removeItem("sei-bi-user");
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        isAuthenticated: Boolean(token),
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth() {
  return useContext(AuthContext);
}
