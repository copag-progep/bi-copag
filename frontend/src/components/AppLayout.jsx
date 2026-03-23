import { Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import FilterBar from "./FilterBar";
import Sidebar from "./Sidebar";


const analyticRoutes = new Set([
  "/",
  "/entradas-saidas",
  "/produtividade",
  "/processos-parados",
  "/multiplos-setores",
]);


export default function AppLayout() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem("sei-bi-sidebar-collapsed") === "true";
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem("sei-bi-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
      />

      <main className="content-shell">
        <header className="topbar">
          <button type="button" className="menu-toggle" onClick={() => setSidebarOpen((value) => !value)}>
            Menu
          </button>

          <div className="topbar-copy">
            <p className="eyebrow">Gestão administrativa</p>
            <h2>Painel operacional do SEI</h2>
          </div>

          <div className="user-chip">
            <span>{user?.name || "Usuário"}</span>
            <small>{user?.email}</small>
          </div>
        </header>

        {analyticRoutes.has(pathname) ? <FilterBar /> : null}

        <section className="page-shell">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
