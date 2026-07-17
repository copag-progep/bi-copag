import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const icons = {
  executive:    { d: ["M4 19V5", "M4 19h16", "M8 15l3-3 3 2 5-7", "M18 7h-4", "M18 7v4"] },
  dashboard:    { d: ["M3 3h7v7H3z", "M14 3h7v7h-7z", "M14 14h7v7h-7z", "M3 14h7v7H3z"] },
  profile:      { d: ["M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2", "M12 11a4 4 0 100-8 4 4 0 000 8z"] },
  servidores:   { d: ["M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2", "M9 7a4 4 0 100 8 4 4 0 000-8z", "M22 21v-2a4 4 0 00-3-3.87", "M16 3.13a4 4 0 010 7.75", "M19 8l2 2-2 2"] },
  upload:       { d: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" },
  flow:         { d: ["M17 3l4 4-4 4", "M3 7h18", "M7 21l-4-4 4-4", "M21 17H3"] },
  prod:         { d: ["M18 20V10", "M12 20V4", "M6 20v-6"] },
  stale:        { d: ["M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z", "M12 6v6l4 2"] },
  multi:        { d: ["M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z", "M12 10a1 1 0 100-2 1 1 0 000 2z"] },
  monthly:      { d: ["M8 2v4", "M16 2v4", "M3 10h18", "M3 6a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6z"] },
  atribuicoes:  { d: ["M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2", "M9 7a4 4 0 100 8 4 4 0 000-8", "M22 21v-2a4 4 0 00-3-3.87", "M16 3.13a4 4 0 010 7.75"] },
  risco:        { d: ["M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z", "M12 8v4", "M12 16h.01"] },
  pauta:        { d: ["M9 11l3 3L22 4", "M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"] },
  users:        { d: ["M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2", "M9 11a4 4 0 100-8 4 4 0 000 8z", "M23 21v-2a4 4 0 00-3-3.87", "M16 3.13a4 4 0 010 7.75"] },
  admin:        { d: ["M12 2a10 10 0 100 20A10 10 0 0012 2z", "M12 8v4", "M12 16h.01"] },
  docs:         { d: ["M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z", "M14 2v6h6", "M16 13H8", "M16 17H8", "M10 9H8"] },
  logout:       { d: ["M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4", "M16 17l5-5-5-5", "M21 12H9"] },
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

const menuGroups = [
  {
    label: "Operacional",
    items: [
      { to: "/",              label: "Área de Trabalho",  icon: "dashboard", end: true },
      { to: "/executivo",     label: "Central Executiva", icon: "executive" },
      { to: "/pauta",         label: "Pauta Prioritária", icon: "pauta" },
      { to: "/risco",         label: "Score de Risco",    icon: "risco" },
      { to: "/atribuicoes",   label: "Atribuições",       icon: "atribuicoes" },
    ],
  },
  {
    label: "Análise",
    items: [
      { to: "/entradas-saidas",     label: "Desempenho",          icon: "flow", activePaths: ["/entradas-saidas", "/produtividade"] },
      { to: "/multiplos-setores",   label: "Inconsistências",     icon: "multi" },
      { to: "/servidores",          label: "Pessoas",             icon: "servidores" },
      { to: "/indicadores-mensais", label: "Indicadores Mensais", icon: "monthly" },
    ],
  },
  {
    label: "Administração",
    items: [
      { to: "/enviar-relatorio", label: "Gestão de Dados", icon: "upload", requiresUpload: true },
      { to: "/administracao",    label: "Administração",  icon: "admin", adminOnly: true, activePaths: ["/administracao", "/usuarios-sei"] },
    ],
  },
];

const utilityItems = [
  { to: "/minha-conta",  label: "Minha Conta",  icon: "profile" },
  { to: "/documentacao", label: "Documentação", icon: "docs" },
];


export default function Sidebar({ open, collapsed, onClose, onToggleCollapse }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const canSee = (item) => {
    if (item.adminOnly && !user?.is_admin) return false;
    if (item.requiresUpload && !user?.is_admin && !user?.can_upload) return false;
    return true;
  };

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
        <p className="eyebrow">AnalyticSEI</p>
        {collapsed ? (
          <h1 style={{ marginTop: 4 }}>SEI</h1>
        ) : (
          <>
            <h1>AnalyticSEI</h1>
            <span>COPAG · PROGEP · UFC</span>
          </>
        )}
      </div>

      <div className="sidebar-scroll">
        <nav className="menu" aria-label="Navegação principal">
          {menuGroups.map((group) => {
            const items = group.items.filter(canSee);
            if (items.length === 0) return null;
            return (
              <div className="menu-group" key={group.label}>
                {!collapsed ? <p className="menu-group-label">{group.label}</p> : <span className="menu-group-divider" />}
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={onClose}
                    title={collapsed ? item.label : undefined}
                    aria-label={collapsed ? item.label : undefined}
                    className={({ isActive }) => `menu-link ${isActive || item.activePaths?.includes(pathname) ? "active" : ""}`}
                  >
                    <Icon name={item.icon} size={18} />
                    {!collapsed ? <span>{item.label}</span> : null}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
      </div>

      {!collapsed && (
        <div className="sidebar-user">
          <div className="user-name">{user?.name || user?.email || "Usuário"}</div>
          <div className="user-role">{user?.is_admin ? "Administrador" : "Servidor"}</div>
          <div className="sidebar-utilities">
            {utilityItems.map((item) => (
              <NavLink key={item.to} to={item.to} onClick={onClose} className="sidebar-utility-link">
                <Icon name={item.icon} size={14} />
                {item.label}
              </NavLink>
            ))}
          </div>
          <NavLink to="/logout" className="sidebar-logout" onClick={onClose}>
            <Icon name="logout" size={14} />
            Sair
          </NavLink>
        </div>
      )}

    </aside>
  );
}
