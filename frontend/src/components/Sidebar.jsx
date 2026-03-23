import { NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const menuItems = [
  { to: "/", label: "Dashboard", shortLabel: "DB", end: true },
  { to: "/enviar-relatorio", label: "Enviar Relat\u00f3rio", shortLabel: "ER" },
  { to: "/entradas-saidas", label: "Entradas e Sa\u00eddas", shortLabel: "ES" },
  { to: "/produtividade", label: "Produtividade", shortLabel: "PR" },
  { to: "/processos-parados", label: "Processos Parados", shortLabel: "PP" },
  { to: "/multiplos-setores", label: "M\u00faltiplos Setores", shortLabel: "MS" },
  { to: "/administracao", label: "Administra\u00e7\u00e3o", shortLabel: "AD", adminOnly: true },
  { to: "/logout", label: "Logout", shortLabel: "SAIR" },
];


export default function Sidebar({ open, collapsed, onClose, onToggleCollapse }) {
  const { user } = useAuth();
  const visibleItems = menuItems.filter((item) => !item.adminOnly || user?.is_admin);

  return (
    <aside className={`sidebar ${open ? "open" : ""} ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-toolbar">
        <button
          type="button"
          className="sidebar-collapse-button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expandir menu lateral" : "Recolher menu lateral"}
          title={collapsed ? "Expandir menu lateral" : "Recolher menu lateral"}
        >
          {collapsed ? ">>" : "<<"}
        </button>
      </div>

      <div className="brand-panel">
        <p className="eyebrow">SEI BI</p>
        <h1>{collapsed ? "COPAG" : "Monitoramento COPAG"}</h1>
        {!collapsed ? <span>Dashboards inteligentes para snapshots di\u00e1rios do SEI</span> : null}
      </div>

      <nav className="menu">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onClose}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) => `menu-link ${isActive ? "active" : ""}`}
          >
            {collapsed ? item.shortLabel : item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
