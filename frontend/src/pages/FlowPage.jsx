import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import PerformanceTabs from "../components/PerformanceTabs";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";


const IcoArrowIn = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
  </svg>
);
const IcoArrowOut = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>
  </svg>
);
const IcoBalance = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="20" x2="12" y2="10"/><path d="M18 20V4"/><path d="M6 20v-4"/>
  </svg>
);


export default function FlowPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/entries-exits",
    toQueryParams()
  );

  if (loading) return <div className="page-grid"><PerformanceTabs /><LoadingBlock label="Calculando entradas e saídas..." /></div>;
  if (error) return <div className="page-grid"><PerformanceTabs /><ErrorBlock message={error} onRetry={retry} /></div>;

  const totalEntradas = (data?.resumo_setorial || []).reduce((acc, item) => acc + item.entradas, 0);
  const totalSaidas   = (data?.resumo_setorial || []).reduce((acc, item) => acc + item.saidas, 0);
  const totalSaldo    = (data?.resumo_setorial || []).reduce((acc, item) => acc + item.saldo, 0);
  const saldoPositivo = totalSaldo > 0;

  return (
    <div className="page-grid">
      <PerformanceTabs />
      <section className="hero-panel flow-hero">
        <div className="ms-hero-body">
          <p className="eyebrow">Entradas e saídas</p>
          <h1>Fluxo diário por setor</h1>
          <div className="flow-hero-dates">
            <span className="flow-date-from">{data?.data_anterior || "—"}</span>
            <svg className="flow-arrow" width="18" height="18" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
            </svg>
            <span className="flow-date-to">{data?.data_referencia || "—"}</span>
          </div>
          {stale && <span className="stale-badge">Atualizando...</span>}
        </div>

        <div className="flow-hero-metrics">
          <div className="flow-metric-item flow-metric-in">
            <span className="flow-metric-val">+{totalEntradas}</span>
            <span className="flow-metric-lbl">entradas</span>
          </div>
          <div className="flow-metric-sep" />
          <div className="flow-metric-item flow-metric-out">
            <span className="flow-metric-val">−{totalSaidas}</span>
            <span className="flow-metric-lbl">saídas</span>
          </div>
          <div className="flow-metric-sep" />
          <div className={`flow-metric-item flow-metric-balance ${saldoPositivo ? "positive" : totalSaldo < 0 ? "negative" : ""}`}>
            <span className="flow-metric-val">{saldoPositivo ? `+${totalSaldo}` : totalSaldo}</span>
            <span className="flow-metric-lbl">saldo</span>
          </div>
        </div>
      </section>

      {data?.comparacao_disponivel === false ? (
        <section className="flow-comparison-notice neutral" role="status">
          <strong>Comparação ainda indisponível</strong>
          <span>Não há snapshot anterior para comparar com {data?.data_referencia || "a referência selecionada"}. Os indicadores de entrada e saída permanecem zerados.</span>
        </section>
      ) : null}

      {data?.setores_sem_base_anterior?.length ? (
        <section className="flow-comparison-notice warning" role="status">
          <strong>Base anterior incompleta</strong>
          <span>{data.setores_sem_base_anterior.join(", ")} não possui snapshot na data anterior. Os registros atuais desses setores são tratados como entradas de base.</span>
        </section>
      ) : null}

      <section className="stats-grid stats-grid-3">
        <StatCard
          icon={<IcoArrowIn />}
          label="Entradas do dia"
          value={totalEntradas}
          hint="Processos recebidos"
        />
        <StatCard
          icon={<IcoArrowOut />}
          label="Saídas do dia"
          value={totalSaidas}
          hint="Processos despachados"
        />
        <StatCard
          icon={<IcoBalance />}
          label="Saldo do dia"
          value={saldoPositivo ? `+${totalSaldo}` : totalSaldo}
          hint={saldoPositivo ? "Acúmulo de carga" : totalSaldo < 0 ? "Redução de carga" : "Equilíbrio"}
        />
      </section>

      <section className="charts-grid">
        <BarChartCard title="Entradas por setor" data={data?.entradas_por_setor || []} />
        <BarChartCard title="Saídas por setor"   data={data?.saidas_por_setor || []}  color="#f39320" />
        <BarChartCard title="Saldo por setor"    data={data?.saldo_por_setor || []}   color="#273168" />
        <LineChartCard
          title="Evolução diária da carga por setor"
          data={data?.evolucao_fluxo || []}
          xKey="date"
          valueKey="carga"
          seriesKey="setor"
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Resumo setorial</h3>
            <p>Entradas, saídas, saldo e carga atual por setor.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "setor", label: "Setor" },
            { key: "entradas", label: "Entradas" },
            { key: "saidas", label: "Saídas" },
            {
              key: "saldo",
              label: "Saldo",
              render: (v) => (
                <span style={{
                  fontWeight: 700,
                  color: v > 0 ? "var(--danger)" : v < 0 ? "var(--success)" : "var(--muted)",
                }}>
                  {v > 0 ? `+${v}` : v}
                </span>
              ),
            },
            { key: "carga_atual", label: "Carga atual" },
          ]}
          rows={data?.resumo_setorial || []}
        />
      </section>
    </div>
  );
}
