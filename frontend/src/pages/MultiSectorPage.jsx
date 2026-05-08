import { useMemo, useState } from "react";

import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";


const SECTOR_STYLES = {
  "DIAPE":            { bg: "rgba(129,199,238,0.16)", color: "#1f6fa0", border: "rgba(129,199,238,0.38)" },
  "DICAT":            { bg: "rgba(243,147,32,0.13)",  color: "#b85e08", border: "rgba(243,147,32,0.32)" },
  "DIJOR":            { bg: "rgba(26,122,80,0.1)",    color: "#176644", border: "rgba(26,122,80,0.28)" },
  "DICAF":            { bg: "rgba(39,49,104,0.1)",    color: "#273168", border: "rgba(39,49,104,0.24)" },
  "DICAF-CHEFIA":     { bg: "rgba(254,187,18,0.16)",  color: "#7a5200", border: "rgba(254,187,18,0.38)" },
  "DICAF-REPOSICOES": { bg: "rgba(90,99,144,0.1)",    color: "#4a5280", border: "rgba(90,99,144,0.24)" },
};

const FALLBACK_STYLE = { bg: "rgba(39,49,104,0.07)", color: "#5a6390", border: "rgba(39,49,104,0.18)" };

function SectorTag({ name }) {
  const s = SECTOR_STYLES[name] || FALLBACK_STYLE;
  return (
    <span
      className="ms-sector-tag"
      style={{ background: s.bg, color: s.color, borderColor: s.border }}
    >
      {name}
    </span>
  );
}

function CountBadge({ count }) {
  const variant = count >= 4 ? "high" : count === 3 ? "mid" : "low";
  return <span className={`ms-count-badge ms-count-badge--${variant}`}>{count}</span>;
}


export default function MultiSectorPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/multi-sector",
    toQueryParams()
  );
  const [search, setSearch] = useState("");

  const processos = data?.processos || [];

  const stats = useMemo(() => {
    const em2     = processos.filter(p => (p.setores?.length ?? 0) === 2).length;
    const em3mais = processos.filter(p => (p.setores?.length ?? 0) >= 3).length;
    const setoresUnicos = new Set(processos.flatMap(p => p.setores || [])).size;
    return { em2, em3mais, setoresUnicos };
  }, [processos]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return processos;
    return processos.filter(p => p.protocolo?.toLowerCase().includes(q));
  }, [processos, search]);

  if (loading) return <LoadingBlock label="Investigando múltiplos setores..." />;
  if (error)   return <ErrorBlock message={error} onRetry={retry} />;

  const total = processos.length;

  return (
    <div className="page-grid">

      {/* ── Hero ── */}
      <section className="hero-panel ms-hero">
        <div className="ms-hero-body">
          <p className="eyebrow">Consistência do snapshot</p>
          <h1>Processos em múltiplos setores</h1>
          <p className="ms-hero-sub">
            Protocolos que aparecem em mais de um setor no mesmo dia.
          </p>
          {total > 0 && (
            <p className="ms-hero-breakdown">
              <span>{stats.em2} em 2 setores</span>
              <span className="ms-hero-dot" />
              <span>{stats.em3mais} em 3 ou mais setores</span>
            </p>
          )}
          {stale && <span className="stale-badge">Atualizando...</span>}
        </div>

        <div className="ms-hero-kpi">
          <span className="ms-hero-kpi-value">{total}</span>
          <span className="ms-hero-kpi-label">
            {total === 1 ? "ocorrência" : "ocorrências"}
          </span>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="stats-grid">
        <StatCard label="Total de ocorrências"   value={total} />
        <StatCard label="Em 2 setores"           value={stats.em2} />
        <StatCard label="Em 3 ou mais setores"   value={stats.em3mais} />
        <StatCard label="Setores envolvidos"      value={stats.setoresUnicos} />
      </section>

      {/* ── Tabela ── */}
      <section className="panel">
        <div className="panel-header ms-panel-header">
          <div>
            <h3>Ocorrências para {data?.data_referencia || "a data selecionada"}</h3>
            <p>Use o filtro de data no topo para analisar snapshots específicos.</p>
          </div>
          <div className="ms-search-wrap">
            <svg className="ms-search-icon" width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.2"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="ms-search"
              placeholder="Buscar protocolo..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            {search
              ? `Nenhum protocolo corresponde a "${search}".`
              : "Nenhum processo encontrado em múltiplos setores com os filtros atuais."}
          </div>
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table ms-table">
                <thead>
                  <tr>
                    <th>Protocolo</th>
                    <th>Setores</th>
                    <th className="ms-col-qty">Qtd</th>
                    <th>Data do relatório</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, i) => (
                    <tr key={row.protocolo || i}>
                      <td>
                        <span className="ms-protocol">{row.protocolo}</span>
                      </td>
                      <td>
                        <div className="ms-tags">
                          {(row.setores || []).map(s => (
                            <SectorTag key={s} name={s} />
                          ))}
                        </div>
                      </td>
                      <td className="ms-col-qty">
                        <CountBadge count={row.setores?.length ?? 0} />
                      </td>
                      <td className="ms-date-cell">{row.data_relatorio}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {search && filtered.length < total && (
              <p className="ms-search-summary">
                Mostrando {filtered.length} de {total} ocorrências
              </p>
            )}
          </>
        )}
      </section>

    </div>
  );
}
