import api from "../api/client";
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


export default function DashboardPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/dashboard",
    toQueryParams()
  );

  if (loading) return <LoadingBlock label="Montando dashboard principal..." />;
  if (error) return <ErrorBlock message={error} onRetry={retry} />;

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Dashboard principal</p>
          <h1>Visão executiva da tramitação</h1>
          <span>Data de referência: {data?.data_referencia || "Sem snapshots importados"}</span>
          {stale ? <span className="stale-badge">Atualizando...</span> : null}
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Processos ativos" value={data?.kpis?.total_processos_ativos ?? 0} />
        <StatCard label="Registros no snapshot" value={data?.kpis?.total_registros_snapshot ?? 0} />
        <StatCard label="Setores ativos" value={data?.kpis?.setores_ativos ?? 0} />
        <StatCard label="Em múltiplos setores" value={data?.kpis?.duplicidades_multissetor ?? 0} />
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
