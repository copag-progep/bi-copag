import { NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const icons = {
  dashboard: { d: ["M3 3h7v7H3z", "M14 3h7v7h-7z", "M14 14h7v7h-7z", "M3 14h7v7H3z"] },
  upload:    { d: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" },
  flow:      { d: ["M17 3l4 4-4 4", "M3 7h18", "M7 21l-4-4 4-4", "M21 17H3"] },
  prod:      { d: ["M18 20V10", "M12 20V4", "M6 20v-6"] },
  stale:     { d: ["M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z", "M12 6v6l4 2"] },
  multi:     { d: ["M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z", "M12 10a1 1 0 100-2 1 1 0 000 2z"] },
  monthly:   { d: ["M8 2v4", "M16 2v4", "M3 10h18", "M3 6a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6z"] },
  users:     { d: ["M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2", "M9 11a4 4 0 100-8 4 4 0 000 8z", "M23 21v-2a4 4 0 00-3-3.87", "M16 3.13a4 4 0 010 7.75"] },
  admin:     { d: ["M12 2a10 10 0 100 20A10 10 0 0012 2z", "M12 8v4", "M12 16h.01"] },
  logout:    { d: ["M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4", "M16 17l5-5-5-5", "M21 12H9"] },
};

function Icon({ name, size = 18 }) {
  const { d } = icons[name] || icons.dashboard;
  const paths = Array.isArray(d) ? d : [d];
  return (
    <svg
      className="menu-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}

const menuItems = [
  { to: "/",                    label: "Dashboard",           icon: "dashboard", end: true },
  { to: "/enviar-relatorio",    label: "Enviar Relatório",    icon: "upload" },
  { to: "/entradas-saidas",     label: "Entradas e Saídas",   icon: "flow" },
  { to: "/produtividade",       label: "Produtividade",       icon: "prod" },
  { to: "/processos-parados",   label: "Processos Parados",   icon: "stale" },
  { to: "/multiplos-setores",   label: "Múltiplos Setores",   icon: "multi" },
  { to: "/indicadores-mensais", label: "Indicadores Mensais", icon: "monthly" },
  { to: "/usuarios-sei",        label: "Usuários SEI",        icon: "users",  adminOnly: true },
  { to: "/administracao",       label: "Administração",       icon: "admin",  adminOnly: true },
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
          aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      <div className="brand-panel">
        <p className="eyebrow">SEI BI</p>
        {collapsed ? (
          <h1 style={{ marginTop: 4 }}>COP</h1>
        ) : (
          <>
            <h1>COPAG</h1>
            <span>UFC · Monitoramento SEI</span>
          </>
        )}
      </div>

      <div className="sidebar-scroll">
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
              <Icon name={item.icon} size={18} />
              {collapsed ? (
                <span style={{ fontSize: "0.55rem", fontWeight: 700, letterSpacing: "0.04em" }}>
                  {item.label.substring(0, 2).toUpperCase()}
                </span>
              ) : (
                item.label
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {!collapsed && (
        <div className="sidebar-user">
          <div className="user-name">{user?.name || user?.email || "Usuário"}</div>
          <div className="user-role">{user?.is_admin ? "Administrador" : "Servidor"}</div>
          <NavLink to="/logout" className="sidebar-logout" onClick={onClose}>
            <Icon name="logout" size={14} />
            Sair
          </NavLink>
        </div>
      )}

    </aside>
  );
}
