import { Fragment, useState } from "react";
import { Link } from "react-router-dom";

import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";


const NIVEL_LABEL = {
  critico:  "Crítico",
  elevado:  "Elevado",
  moderado: "Moderado",
  normal:   "Normal",
};

const NUMBER_FORMATTER = new Intl.NumberFormat("pt-BR");
function fmt(v) { return NUMBER_FORMATTER.format(Number(v || 0)); }
function rowId(proc) {
  return `${proc.protocolo}|${proc.setor}|${proc.entrada_setor || ""}`;
}

function RiskBadge({ nivel }) {
  return <span className={`risk-badge risk-badge-${nivel}`}>{NIVEL_LABEL[nivel] || nivel}</span>;
}

function ScoreBar({ score, nivel }) {
  const pct = Math.round(score * 100);
  return (
    <div className="risk-score-bar" title={`Score: ${pct}/100`}>
      <div className={`risk-score-fill risk-score-fill-${nivel}`} style={{ width: `${pct}%` }} />
      <span className="risk-score-label">{pct}</span>
    </div>
  );
}

function FactorBar({ label, contribuicao, maxContribuicao, detalhe }) {
  if (contribuicao <= 0 && !detalhe) return null;
  const pct = maxContribuicao > 0 ? Math.min((contribuicao / maxContribuicao) * 100, 100) : 0;
  return (
    <div className="risk-factor-item">
      <div className="risk-factor-header">
        <span className="risk-factor-label">{label}</span>
        <span className="risk-factor-pts">+{Math.round(contribuicao * 100)}pts</span>
      </div>
      <div className="risk-factor-track">
        <div className="risk-factor-fill" style={{ width: `${pct}%` }} />
      </div>
      {detalhe && <p className="risk-factor-detail">{detalhe}</p>}
    </div>
  );
}

function ProcessBreakdown({ proc }) {
  const { fatores } = proc;
  const scoreLabel = Math.round(proc.score * 100);
  const { multiplicador, detalhe: tDetalhe } = fatores.tendencia_setor;

  return (
    <div className="risk-breakdown">
      <div className="risk-breakdown-intro">
        <RiskBadge nivel={proc.nivel} />
        <strong>Score {scoreLabel}/100</strong>
        <span>· {proc.protocolo}</span>
      </div>

      <div className="risk-breakdown-factors">
        <FactorBar
          label="Tempo no setor"
          contribuicao={fatores.tempo_absoluto.contribuicao}
          maxContribuicao={0.40}
          detalhe={fatores.tempo_absoluto.detalhe}
        />
        <FactorBar
          label="Contexto histórico (P90)"
          contribuicao={fatores.tempo_relativo.contribuicao}
          maxContribuicao={0.35}
          detalhe={fatores.tempo_relativo.detalhe}
        />
        <FactorBar
          label="Sem atribuição"
          contribuicao={fatores.sem_atribuicao.contribuicao}
          maxContribuicao={0.15}
          detalhe={fatores.sem_atribuicao.detalhe}
        />
        <FactorBar
          label="Múltiplos setores"
          contribuicao={fatores.multiplos_setores.contribuicao}
          maxContribuicao={0.10}
          detalhe={fatores.multiplos_setores.detalhe}
        />
      </div>

      {multiplicador !== 1.0 && tDetalhe && (
        <div className="risk-trend-note">
          <span>Multiplicador de tendência: <strong>{multiplicador}×</strong></span>
          <span>{tDetalhe}</span>
        </div>
      )}

      <div className="risk-breakdown-footer">
        <Link to="/atribuicoes" className="link-secondary">
          Ver carteira completa →
        </Link>
      </div>
    </div>
  );
}

const NIVEIS = ["todos", "critico", "elevado", "moderado", "normal"];

export default function RiscoPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, error, retry } = useAnalyticsData(
    "/analytics/risk-score",
    toQueryParams()
  );
  const [nivelFiltro, setNivelFiltro] = useState("todos");
  const [expanded, setExpanded] = useState(null);

  if (loading) return <LoadingBlock label="Calculando scores de risco..." />;
  if (error)   return <ErrorBlock message={error} onRetry={retry} />;

  const riskData  = data || {};
  const all       = riskData.processos || [];
  const contagens = riskData.contagens  || {};
  const filtered  = nivelFiltro === "todos"
    ? all
    : all.filter((p) => p.nivel === nivelFiltro);

  function toggleRow(id) {
    setExpanded((prev) => (prev === id ? null : id));
  }

  return (
    <div className="page-grid">
      <section className="hero-panel risk-hero">
        <div>
          <p className="eyebrow">Gestão executiva</p>
          <h1>Score de Risco</h1>
          <p>
            Processos priorizados por urgência estimada.
            Score calculado sobre o processo — não sobre o servidor.
          </p>
        </div>
        <div className="risk-hero-kpis">
          {(["critico", "elevado", "moderado"] ).map((n) => (
            <div key={n} className={`risk-hero-kpi risk-hero-kpi-${n}`}>
              <strong>{fmt(contagens[n] || 0)}</strong>
              <span>{NIVEL_LABEL[n]}</span>
            </div>
          ))}
        </div>
      </section>

      {!riskData.cobertura_lead_time && all.length > 0 && (
        <div className="risk-coverage-notice">
          Fator de contexto histórico (P90) não aplicado — histórico de lead time insuficiente.
          Score baseado em tempo absoluto, atribuição e presença em múltiplos setores.
        </div>
      )}

      <section className="panel risk-filter-section">
        <div className="risk-filter-pills">
          {NIVEIS.map((n) => (
            <button
              key={n}
              type="button"
              className={`risk-filter-pill ${nivelFiltro === n ? "active" : ""} ${n !== "todos" ? `pill-nivel-${n}` : ""}`}
              onClick={() => { setNivelFiltro(n); setExpanded(null); }}
            >
              {n === "todos"
                ? `Todos (${all.length})`
                : `${NIVEL_LABEL[n]} (${contagens[n] || 0})`}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        {filtered.length === 0 ? (
          <div className="empty-state">Nenhum processo encontrado para este filtro.</div>
        ) : (
          <div className="table-shell">
            <table className="data-table risk-table">
              <thead>
                <tr>
                  <th>Protocolo</th>
                  <th>Setor</th>
                  <th>Atribuição</th>
                  <th>Tipo</th>
                  <th>Dias</th>
                  <th>Score</th>
                  <th>Nível</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((proc) => {
                  const id = rowId(proc);
                  return (
                    <Fragment key={id}>
                      <tr
                        className={`risk-row ${expanded === id ? "risk-row-open" : ""}`}
                        onClick={() => toggleRow(id)}
                        title="Clique para ver detalhes do score"
                      >
                        <td className="risk-protocolo">{proc.protocolo}</td>
                        <td>{proc.setor}</td>
                        <td>
                          {proc.atribuicao
                            ? proc.atribuicao
                            : <span className="risk-sem-atrib">Sem atribuição</span>}
                        </td>
                        <td>{proc.tipo || "—"}</td>
                        <td><strong>{fmt(proc.dias_no_setor)}</strong></td>
                        <td><ScoreBar score={proc.score} nivel={proc.nivel} /></td>
                        <td><RiskBadge nivel={proc.nivel} /></td>
                      </tr>
                      {expanded === id && (
                        <tr className="risk-breakdown-row">
                          <td colSpan={7}>
                            <ProcessBreakdown proc={proc} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="risk-disclaimer">
        {riskData.nota}
        {riskData.pesos && (
          <span>
            {" "}· Pesos: tempo {riskData.pesos.tempo_absoluto * 100}%
            + contexto {riskData.pesos.tempo_relativo * 100}%
            + atribuição {riskData.pesos.sem_atribuicao * 100}%
            + multi-setor {riskData.pesos.multiplos_setores * 100}%
          </span>
        )}
      </div>
    </div>
  );
}
