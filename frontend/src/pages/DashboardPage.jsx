import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import PieChartCard from "../charts/PieChartCard";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { formatUserNameAsInitials } from "../utils/userNameFormatter";


const IcoFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
  </svg>
);
const IcoLayers = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
  </svg>
);
const IcoGrid = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
);
const IcoAlert = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);


export default function DashboardPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/dashboard",
    toQueryParams()
  );

  if (loading) return <LoadingBlock label="Montando dashboard principal..." />;
  if (error) return <ErrorBlock message={error} onRetry={retry} />;

  const duplicidades = data?.kpis?.duplicidades_multissetor ?? 0;

  return (
    <div className="page-grid">
      <section className="hero-panel ms-hero">
        <div className="ms-hero-body">
          <p className="eyebrow">Dashboard principal</p>
          <h1>Visão executiva da tramitação</h1>
          <p className="ms-hero-sub">
            Data de referência: {data?.data_referencia || "Sem snapshots importados"}
          </p>
          {duplicidades > 0 && (
            <p className="ms-hero-breakdown">
              <span className="dash-alert-pill">
                ⚠ {duplicidades} {duplicidades === 1 ? "processo" : "processos"} em múltiplos setores
              </span>
            </p>
          )}
          {stale && <span className="stale-badge">Atualizando...</span>}
        </div>
        <div className="ms-hero-kpi">
          <span className="ms-hero-kpi-value">{data?.kpis?.total_processos_ativos ?? 0}</span>
          <span className="ms-hero-kpi-label">processos ativos</span>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard
          icon={<IcoFile />}
          label="Processos ativos"
          value={data?.kpis?.total_processos_ativos ?? 0}
          hint="No snapshot atual"
        />
        <StatCard
          icon={<IcoLayers />}
          label="Registros no snapshot"
          value={data?.kpis?.total_registros_snapshot ?? 0}
          hint="Total de linhas importadas"
        />
        <StatCard
          icon={<IcoGrid />}
          label="Setores ativos"
          value={data?.kpis?.setores_ativos ?? 0}
          hint="Com processos no snapshot"
        />
        <StatCard
          icon={<IcoAlert />}
          label="Em múltiplos setores"
          value={duplicidades}
          hint={duplicidades > 0 ? "Requer verificação" : "Consistente"}
        />
      </section>

      <section className="charts-grid">
        <BarChartCard title="Processos por setor" data={data?.por_setor || []} />
        <PieChartCard title="Processos por tipo" data={(data?.por_tipo || []).slice(0, 8)} />
        <BarChartCard
          title="Ranking de atribuições"
          data={(data?.ranking_atribuicoes || []).slice(0, 10)}
          color="#f39320"
          tickFormatter={formatUserNameAsInitials}
        />
        <LineChartCard
          title="Evolução diária do total de processos"
          data={data?.evolucao_diaria || []}
          xKey="date"
          valueKey="value"
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Atribuições com mais finalizações</h3>
            <p>Contagem de saídas inferidas a partir dos snapshots históricos.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "label", label: "Atribuição" },
            { key: "value", label: "Processos finalizados" },
          ]}
          rows={data?.ranking_atribuicoes_finalizadas || []}
          emptyMessage="Ainda não há histórico suficiente para calcular finalizações."
        />
      </section>
    </div>
  );
}
