export default function StatCard({ label, value, hint, icon, trend, trendUp }) {
  return (
    <article className="stat-card">
      {(icon || trend) && (
        <div className="stat-card-header">
          {icon && <div className="stat-card-icon">{icon}</div>}
          {trend && (
            <span className={`stat-card-trend ${trendUp ? "up" : "down"}`}>
              {trendUp ? "↑" : "↓"} {trend}
            </span>
          )}
        </div>
      )}
      <div>
        <strong>{value}</strong>
        <p className="stat-label">{label}</p>
        {hint ? <small>{hint}</small> : null}
      </div>
    </article>
  );
}
