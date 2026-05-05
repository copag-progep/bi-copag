import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import FilterBar from "./FilterBar";
import Sidebar from "./Sidebar";


const analyticRoutes = new Set([
  "/",
  "/entradas-saidas",
  "/produtividade",
  "/multiplos-setores",
  "/atribuicoes",
  "/servidores",
]);

const pageTitles = {
  "/":                    { eyebrow: "Visão geral",       title: "Dashboard" },
  "/enviar-relatorio":    { eyebrow: "Gestão de dados",   title: "Enviar Relatório" },
  "/entradas-saidas":     { eyebrow: "Fluxo diário",      title: "Entradas e Saídas" },
  "/produtividade":       { eyebrow: "Desempenho",        title: "Produtividade" },
  "/multiplos-setores":   { eyebrow: "Consistência",      title: "Múltiplos Setores" },
  "/atribuicoes":         { eyebrow: "Carteiras",         title: "Atribuições" },
  "/servidores":          { eyebrow: "Gestão de carga",   title: "Servidores" },
  "/indicadores-mensais": { eyebrow: "Relatórios",        title: "Indicadores Mensais" },
  "/usuarios-sei":        { eyebrow: "Configuração",      title: "Usuários SEI" },
  "/administracao":       { eyebrow: "Sistema",           title: "Administração" },
  "/minha-conta":         { eyebrow: "Conta",             title: "Minha conta" },
  "/busca":               { eyebrow: "Busca global",      title: "Localizar processo" },
};


export default function AppLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("sei-bi-sidebar-collapsed") === "true";
  });
  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("sei-bi-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  function handleSearch(e) {
    e.preventDefault();
    const q = searchInput.trim();
    if (q) {
      navigate(`/busca?q=${encodeURIComponent(q)}`);
      setSearchInput("");
    }
  }

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

            {/* Barra de busca global */}
            <form onSubmit={handleSearch} style={{ display: "flex", alignItems: "center" }}>
              <div style={{ position: "relative" }}>
                <svg
                  style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)",
                    opacity: 0.35, pointerEvents: "none" }}
                  width="14" height="14" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Buscar protocolo..."
                  style={{
                    width: 200, border: "1.5px solid var(--border-strong)",
                    borderRadius: 999, padding: "7px 12px 7px 30px",
                    fontSize: "0.8rem", fontFamily: "inherit", color: "var(--ink)",
                    background: "#fafbff", outline: "none",
                  }}
                />
              </div>
            </form>

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
