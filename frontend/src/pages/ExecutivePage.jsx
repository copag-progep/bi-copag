import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import SparklineCard from "../components/SparklineCard";
import api from "../api/client";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";


const NUMBER_FORMATTER = new Intl.NumberFormat("pt-BR");


function formatNumber(value) {
  return NUMBER_FORMATTER.format(Number(value || 0));
}

function formatSigned(value) {
  const normalized = Number(value || 0);
  return normalized > 0 ? `+${formatNumber(normalized)}` : formatNumber(normalized);
}

function formatDate(value) {
  if (!value) return "sem data";
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

function lastValue(series) {
  return series?.length ? series[series.length - 1].value : 0;
}

function aggregateFlowByDate(rows = [], key) {
  const bucket = new Map();
  for (const row of rows) {
    const current = bucket.get(row.date) || 0;
    bucket.set(row.date, current + Number(row[key] || 0));
  }
  return Array.from(bucket.entries()).map(([date, value]) => ({ date, value }));
}

function buildPriorities({ freshness, dashboard, flow, stale }) {
  const priorities = [];
  const critical90 = (stale?.processos || []).filter((item) => item.dias_sem_movimentacao >= 90).length;
  const critical30 = stale?.contagens?.mais_de_30 || 0;
  const duplicates = dashboard?.kpis?.duplicidades_multissetor || 0;
  const overloadedSectors = (flow?.resumo_setorial || [])
    .filter((item) => item.saldo > 0)
    .sort((a, b) => b.saldo - a.saldo)
    .slice(0, 2);

  if (freshness && freshness.status !== "ok") {
    priorities.push({
      type: "Dados",
      title: "Conferir atualização dos snapshots",
      detail: freshness.status === "critical"
        ? `Referência ${formatDate(freshness.data_referencia_global)} está ${freshness.idade_dias} dias atrás.`
        : `${freshness.total_setores_em_dia}/${freshness.total_setores_esperados} setores em dia na referência atual.`,
      to: "/enviar-relatorio",
    });
  }

  if (critical90 > 0) {
      priorities.push({
        type: "Crítico",
        title: `${formatNumber(critical90)} processos com 90 dias ou mais`,
        detail: "Prioridade máxima para evitar represamento prolongado.",
        to: "/atribuicoes",
      });
  } else if (critical30 > 0) {
      priorities.push({
        type: "Atenção",
        title: `${formatNumber(critical30)} processos acima de 30 dias`,
        detail: "Vale revisar a carteira de processos parados.",
        to: "/atribuicoes",
      });
  }

  for (const sector of overloadedSectors) {
    priorities.push({
      type: "Fluxo",
      title: `${sector.setor} acumulou ${formatNumber(sector.saldo)} processos`,
      detail: `${formatNumber(sector.entradas)} entradas e ${formatNumber(sector.saidas)} saídas no período comparado.`,
      to: "/entradas-saidas",
    });
  }

  if (duplicates > 0) {
    priorities.push({
      type: "Consistência",
      title: `${formatNumber(duplicates)} processos em múltiplos setores`,
      detail: "Pode indicar tramitação compartilhada ou inconsistência a conferir.",
      to: "/multiplos-setores",
    });
  }

  return priorities.slice(0, 5);
}


export default function ExecutivePage() {
  const { toQueryParams } = useFilters();
  const params = toQueryParams();
  const dashboard = useAnalyticsData("/analytics/dashboard", params);
  const flow = useAnalyticsData("/analytics/entries-exits", params);
  const baseReady = !dashboard.loading && !flow.loading && !dashboard.error && !flow.error;
  const stale = useAnalyticsData("/analytics/stale", params, { enabled: baseReady, timeout: 120_000 });
  const leadTime = useAnalyticsData("/analytics/lead-time", params, {
    enabled: baseReady && !stale.loading,
    timeout: 120_000,
  });
  // Forecast: carregado sob demanda — não participa do gate de loading/error
  const forecast = useAnalyticsData("/analytics/forecast", params);
  const [freshness, setFreshness] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.get("/health/data-freshness")
      .then((response) => {
        if (!cancelled) setFreshness(response.data);
      })
      .catch(() => {
        if (!cancelled) setFreshness(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (dashboard.loading || flow.loading) {
    return <LoadingBlock label="Montando central executiva..." />;
  }

  const firstError = dashboard.error || flow.error;
  if (firstError) {
    return (
      <ErrorBlock
        message={firstError}
        onRetry={() => {
          dashboard.retry();
          flow.retry();
          stale.retry();
          leadTime.retry();
        }}
      />
    );
  }

  const dashboardData = dashboard.data || {};
  const flowData = flow.data || {};
  const staleData = stale.data || {};

  const activeSeries = dashboardData.evolucao_diaria || [];
  const entriesSeries = aggregateFlowByDate(flowData.evolucao_fluxo, "entradas");
  const exitsSeries = aggregateFlowByDate(flowData.evolucao_fluxo, "saidas");
  const balanceSeries = aggregateFlowByDate(flowData.evolucao_fluxo, "saldo");
  const flowRows = flowData.resumo_setorial || [];

  const totalEntries = flowRows.reduce((acc, item) => acc + item.entradas, 0);
  const totalExits = flowRows.reduce((acc, item) => acc + item.saidas, 0);
  const balance = totalEntries - totalExits;
  const critical30 = staleData.contagens?.mais_de_30 || 0;
  const critical90 = (staleData.processos || []).filter((item) => item.dias_sem_movimentacao >= 90).length;
  const priorities = buildPriorities({
    freshness,
    dashboard: dashboardData,
    flow: flowData,
    stale: staleData,
  });
  const topSectors = [...flowRows].sort((a, b) => b.carga_atual - a.carga_atual).slice(0, 6);
  const criticalProcesses = (staleData.processos || []).slice(0, 5);
  const ltData = leadTime.data || {};
  const ltKpis = ltData.kpis || {};
  const ltSectors = ltData.ranking_setor || [];

  const fData = forecast.data || {};
  const fVol = fData.volume || null;
  const fSetores = fData.setores || [];
  const fCriticos = fData.criticos || null;
  const fNota = fData.nota || "";

  return (
    <div className="page-grid executive-page">
      <section className="hero-panel executive-hero">
        <div>
          <p className="eyebrow">Central executiva</p>
          <h1>Prioridades do dia em uma tela</h1>
          <p>
            Referência {formatDate(dashboardData.data_referencia)}. Uma síntese para decidir.
          </p>
        </div>
        <div className="executive-hero-metric">
          <span>{formatSigned(balance)}</span>
          <small>saldo do dia</small>
        </div>
      </section>

      <section className="executive-spark-grid">
        <SparklineCard
          label="Processos ativos"
          value={dashboardData.kpis?.total_processos_ativos || lastValue(activeSeries)}
          hint="Tendência dos últimos snapshots"
          data={activeSeries}
          color="#273168"
        />
        <SparklineCard
          label="Entradas"
          value={totalEntries}
          hint="Recebidos no último comparativo"
          data={entriesSeries}
          color="#1a7a50"
          tone="success"
        />
        <SparklineCard
          label="Saídas"
          value={totalExits}
          hint="Despachados no último comparativo"
          data={exitsSeries}
          color="#d4750e"
          tone="warning"
        />
        <SparklineCard
          label="Saldo"
          value={balance}
          hint={balance > 0 ? "Carga aumentou" : balance < 0 ? "Carga reduziu" : "Fluxo equilibrado"}
          data={balanceSeries}
          color={balance > 0 ? "#bf3535" : "#1a7a50"}
          tone={balance > 0 ? "danger" : "success"}
        />
      </section>

      <section className="executive-grid">
        <article className="panel executive-priority-panel">
          <div className="panel-header">
            <div>
              <h3>Prioridades do dia</h3>
              <p>Leitura acionável a partir de dados, fluxo e processos críticos.</p>
            </div>
          </div>
          {priorities.length ? (
            <div className="priority-list">
              {priorities.map((item, index) => (
                <Link key={`${item.type}-${index}`} to={item.to} className="priority-item">
                  <span className="priority-type">{item.type}</span>
                  <strong>{item.title}</strong>
                  <small>{item.detail}</small>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state">Nenhuma prioridade crítica encontrada com os filtros atuais.</div>
          )}
        </article>

        <article className="panel executive-health-panel">
          <div className="panel-header">
            <div>
              <h3>Saúde dos dados</h3>
              <p>Completude e idade dos snapshots que alimentam os painéis.</p>
            </div>
          </div>
          <div className={`executive-health-status ${freshness?.status || "loading"}`}>
            <strong>{freshness?.status === "ok" ? "Dados em dia" : "Verificar dados"}</strong>
            <span>
              {freshness
                ? `${freshness.total_setores_em_dia}/${freshness.total_setores_esperados} setores em dia · ${formatDate(freshness.data_referencia_global)}`
                : "Consultando frescor dos dados..."}
            </span>
          </div>
          <div className="executive-mini-metrics">
            <div>
              <strong>{formatNumber(critical30)}</strong>
              <span>+30 dias</span>
            </div>
            <div>
              <strong>{formatNumber(critical90)}</strong>
              <span>+90 dias</span>
            </div>
            <div>
              <strong>{formatNumber(dashboardData.kpis?.duplicidades_multissetor || 0)}</strong>
              <span>multi-setor</span>
            </div>
          </div>
        </article>
      </section>

      {(leadTime.error || ltKpis.finalizados > 0) && (
        <section className="executive-grid">
          <article className="panel executive-lead-time-panel">
            <div className="panel-header">
              <div>
                <h3>Tempo de permanência</h3>
                <p>Lead time estimado dos processos que saíram da carteira.</p>
              </div>
            </div>
            {leadTime.error ? (
              <div className="lead-time-unavailable">
                Lead time indisponível no momento. Os demais indicadores continuam carregados.
              </div>
            ) : (
              <>
                <div className="lead-time-metrics">
                  <div className="lead-time-metric">
                    <strong>{ltKpis.media_dias}</strong>
                    <span>média (dias)</span>
                  </div>
                  <div className="lead-time-metric">
                    <strong>{ltKpis.mediana_dias}</strong>
                    <span>mediana (dias)</span>
                  </div>
                  <div className="lead-time-metric accent">
                    <strong>{ltKpis.p90_dias}</strong>
                    <span>P90 (dias)</span>
                  </div>
                  <div className="lead-time-metric">
                    <strong>{formatNumber(ltKpis.finalizados)}</strong>
                    <span>finalizados</span>
                  </div>
                </div>
                <div className="lead-time-bars">
                  {(ltData.distribuicao_faixas || []).map((item) => {
                    const pct = ltKpis.finalizados ? Math.round((item.quantidade / ltKpis.finalizados) * 100) : 0;
                    return (
                      <div key={item.faixa} className="lead-time-bar-row">
                        <span className="lead-time-bar-label">{item.faixa}d</span>
                        <div className="lead-time-bar-track">
                          <div className="lead-time-bar-fill" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="lead-time-bar-value">{item.quantidade}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </article>

          {!leadTime.error && (
            <article className="panel">
            <div className="panel-header">
              <div>
                <h3>Lead time por setor</h3>
                <p>Setores com maior tempo médio de permanência.</p>
              </div>
            </div>
            <DataTable
              columns={[
                { key: "label", label: "Setor" },
                { key: "media_dias", label: "Média" },
                { key: "mediana_dias", label: "Mediana" },
                { key: "p90_dias", label: "P90" },
                { key: "finalizados", label: "Saíram" },
              ]}
              rows={ltSectors}
              emptyMessage="Sem dados de lead time para o período."
            />
          </article>
          )}
        </section>
      )}

      {fVol && (
        <section className="executive-grid">
          <article className="panel forecast-panel">
            <div className="panel-header">
              <div>
                <h3>Estoque ativo: tendências</h3>
                <p>{fNota}</p>
              </div>
            </div>
            <div className="forecast-volume-grid">
              <div className="forecast-metric">
                <span>Atual</span>
                <strong>{formatNumber(fVol.atual)}</strong>
              </div>
              <div className="forecast-metric forecast-metric-proj">
                <span>Em 15 dias</span>
                <strong>~{formatNumber(fVol.estimado_15d)}</strong>
              </div>
              <div className="forecast-metric forecast-metric-proj">
                <span>Em 30 dias</span>
                <strong>~{formatNumber(fVol.estimado_30d)}</strong>
              </div>
            </div>
            <div className={`forecast-trend-pill forecast-trend-${fVol.tendencia}`}>
              {fVol.tendencia === "crescendo" ? "↑ Crescendo"
                : fVol.tendencia === "reduzindo" ? "↓ Reduzindo"
                : "→ Estável"}
              <span>
                &nbsp;· {fVol.variacao_diaria_media > 0 ? "+" : ""}{fVol.variacao_diaria_media} processos/dia em média
              </span>
            </div>
            {fCriticos && fCriticos.atual_estimado > 0 && (
              <div className="forecast-critical">
                <div className="forecast-critical-row">
                  <div>
                    <strong>{formatNumber(fCriticos.atual_estimado)}</strong>
                    <small>+30 dias agora</small>
                  </div>
                  <span className="forecast-arrow">→</span>
                  <div>
                    <strong>~{formatNumber(fCriticos.estimado_15d)}</strong>
                    <small>estimativa em 15 dias</small>
                  </div>
                </div>
                <p className="forecast-disclaimer">{fCriticos.nota}</p>
              </div>
            )}
          </article>

          <article className="panel">
            <div className="panel-header">
              <div>
                <h3>Tendência por setor</h3>
                <p>Variação média diária e estimativa para 30 dias.</p>
              </div>
            </div>
            <DataTable
              columns={[
                { key: "setor", label: "Setor" },
                { key: "carga_atual", label: "Atual", render: (v) => formatNumber(v) },
                {
                  key: "variacao_diaria_media",
                  label: "Var./dia",
                  render: (v) => (
                    <span className={v > 0 ? "forecast-delta-up" : v < 0 ? "forecast-delta-down" : "forecast-delta-neutral"}>
                      {v > 0 ? `+${v}` : `${v}`}
                    </span>
                  ),
                },
                {
                  key: "tendencia",
                  label: "Tendência",
                  render: (v) => (
                    <span className={`forecast-badge forecast-badge-${v}`}>
                      {v === "acumulando" ? "↑ Acumulando"
                        : v === "resolvendo" ? "↓ Resolvendo"
                        : "→ Estável"}
                    </span>
                  ),
                },
                { key: "estimado_30d", label: "~30 dias", render: (v) => `~${formatNumber(v)}` },
              ]}
              rows={fSetores}
              emptyMessage="Histórico insuficiente para calcular tendências setoriais."
            />
          </article>
        </section>
      )}

      <section className="executive-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <h3>Carga por setor</h3>
              <p>Setores com maior volume de processos ativos no snapshot atual.</p>
            </div>
            <Link className="table-button" to="/entradas-saidas">Ver fluxo</Link>
          </div>
          <DataTable
            columns={[
              { key: "setor", label: "Setor" },
              { key: "carga_atual", label: "Ativos" },
              { key: "entradas", label: "Entradas" },
              { key: "saidas", label: "Saídas" },
              { key: "saldo", label: "Saldo", render: (value) => formatSigned(value) },
            ]}
            rows={topSectors}
          />
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <h3>Processos mais críticos</h3>
              <p>Top 5 por tempo sem movimentação no setor atual.</p>
            </div>
            <Link className="table-button" to="/atribuicoes">Ver carteira</Link>
          </div>
          <DataTable
            columns={[
              { key: "protocolo", label: "Protocolo" },
              { key: "setor", label: "Setor" },
              { key: "dias_sem_movimentacao", label: "Dias" },
            ]}
            rows={criticalProcesses}
            emptyMessage="Nenhum processo crítico encontrado."
          />
        </article>
      </section>
    </div>
  );
}
