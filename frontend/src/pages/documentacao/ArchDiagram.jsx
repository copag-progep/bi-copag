export default function ArchDiagram() {
  const tier = (label, sub, items, color = "#273168") => (
    <div className="arch-tier" style={{ borderColor: color }}>
      <div className="arch-tier-header" style={{ background: color }}>
        <span>{label}</span>
        {sub && <small>{sub}</small>}
      </div>
      <div className="arch-tier-body">
        {items.map((item, i) => (
          <div key={i} className="arch-item">
            <span className="arch-item-dot" style={{ background: color }} />
            {item}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="arch-diagram">
      {tier("Desenvolvimento local", "git push → main", [
        "Edição dos arquivos localmente",
        "git commit + git push para o branch main",
        "GitHub dispara deploys automáticos",
      ], "#273168")}

      <div className="arch-arrow">↓</div>

      <div className="arch-row">
        {tier("Render", "Backend FastAPI", [
          "bi-copag-api.onrender.com",
          "Python 3.12 · FastAPI · SQLAlchemy",
          "pip install + uvicorn restart",
          "Variáveis de ambiente configuradas",
        ], "#f39320")}
        {tier("Vercel", "Frontend React", [
          "bi-copag.vercel.app",
          "React 18 · Vite build",
          "CDN global · npm run build",
          "Rewrite /api/* → Render",
        ], "#1a7a50")}
      </div>

      <div className="arch-arrow">↓</div>

      {tier("Neon DB", "PostgreSQL · AWS us-east-1", [
        "Conexão via connection pooler",
        "6 tabelas · Alembic migrations",
        "0.07 / 0.5 GB (plano gratuito)",
      ], "#4a148c")}

      <div className="arch-arrow">↕</div>

      {tier("GitHub Actions", "5 workflows automáticos", [
        "keep-alive — a cada 10 min",
        "daily-upload — Seg–Sex 19:00 BRT",
        "weekly-report — Sex 20:00 BRT",
        "critical-alerts — Sex 21:00 BRT",
      ], "#81c7ee")}
    </div>
  );
}
