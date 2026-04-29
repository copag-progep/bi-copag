import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

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

const pageTitles = {
  "/":                    { eyebrow: "Visão geral",       title: "Dashboard" },
  "/enviar-relatorio":    { eyebrow: "Gestão de dados",   title: "Enviar Relatório" },
  "/entradas-saidas":     { eyebrow: "Fluxo diário",      title: "Entradas e Saídas" },
  "/produtividade":       { eyebrow: "Desempenho",        title: "Produtividade" },
  "/processos-parados":   { eyebrow: "Alertas críticos",  title: "Processos Parados" },
  "/multiplos-setores":   { eyebrow: "Consistência",      title: "Múltiplos Setores" },
  "/indicadores-mensais": { eyebrow: "Relatórios",        title: "Indicadores Mensais" },
  "/usuarios-sei":        { eyebrow: "Configuração",      title: "Usuários SEI" },
  "/administracao":       { eyebrow: "Sistema",           title: "Administração" },
};


export default function AppLayout() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("sei-bi-sidebar-collapsed") === "true";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("sei-bi-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  const page = pageTitles[pathname] || { eyebrow: "SEI BI", title: "COPAG" };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
      />

      <main className="content-shell">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="eyebrow">{page.eyebrow}</p>
            <h2>{page.title}</h2>
          </div>

          <div className="topbar-actions">
            <button
              type="button"
              className="menu-toggle ghost-button"
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label="Abrir menu"
            >
              ☰ Menu
            </button>
            <div className="user-chip">
              <span>{user?.name || user?.email || "Usuário"}</span>
              <small>{user?.is_admin ? "Administrador" : "Servidor"}</small>
            </div>
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
