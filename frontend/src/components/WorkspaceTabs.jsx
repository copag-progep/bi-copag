import { NavLink } from "react-router-dom";


export default function WorkspaceTabs({ label, tabs }) {
  return (
    <nav className="workspace-tabs" aria-label={label}>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => `workspace-tab ${isActive ? "active" : ""}`}
        >
          {tab.icon ? <span className="workspace-tab-icon" aria-hidden="true">{tab.icon}</span> : null}
          <span>{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
