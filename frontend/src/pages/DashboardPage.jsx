import { Link } from "react-router-dom";

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
    <div className="page-grid priority-workspace">
      <section className="priority-overview-grid">
        <div className="priority-action-panel">
          <div className="priority-action-heading">
            <div>
              <p className="eyebrow">Fila de ação imediata</p>
              <h1>Exceções e prioridades</h1>
              <p>Referência: {data?.data_referencia || "Sem snapshots importados"}</p>
            </div>
            {stale ? <span className="stale-badge">Atualizando...</span> : null}
          </div>

          <div className="priority-action-list">
            <Link to="/multiplos-setores" className={`priority-action-item ${duplicidades > 0 ? "critical" : "resolved"}`}>
              <span className="priority-action-icon"><IcoAlert /></span>
              <span>
                <strong>{duplicidades > 0 ? `${duplicidades} ${duplicidades === 1 ? "processo" : "processos"} em múltiplos setores` : "Nenhuma duplicidade entre setores"}</strong>
                <small>{duplicidades > 0 ? "Requer conferência da tramitação atual." : "A consistência setorial está regular."}</small>
              </span>
              <span className="priority-action-arrow" aria-hidden="true">→</span>
            </Link>
            <Link to="/risco" className="priority-action-item">
              <span className="priority-action-icon"><IcoLayers /></span>
              <span><strong>Revisar processos com maior risco</strong><small>Priorize tempo parado, tipo e grau calculado.</small></span>
              <span className="priority-action-arrow" aria-hidden="true">→</span>
            </Link>
            <Link to="/pauta" className="priority-action-item">
              <span className="priority-action-icon"><IcoFile /></span>
              <span><strong>Acompanhar prazos da Pauta Prioritária</strong><small>Consulte sessões, responsáveis e itens pendentes.</small></span>
              <span className="priority-action-arrow" aria-hidden="true">→</span>
            </Link>
          </div>
        </div>

        <div className="priority-kpi-rail" aria-label="Resumo do snapshot">
          <StatCard icon={<IcoFile />} label="Processos ativos" value={data?.kpis?.total_processos_ativos ?? 0} hint="No snapshot atual" />
          <StatCard icon={<IcoGrid />} label="Setores ativos" value={data?.kpis?.setores_ativos ?? 0} hint="Com processos no snapshot" />
          <StatCard icon={<IcoLayers />} label="Registros totais" value={data?.kpis?.total_registros_snapshot ?? 0} hint="Linhas importadas" />
          <StatCard icon={<IcoAlert />} label="Inconsistências" value={duplicidades} hint={duplicidades > 0 ? "Requer verificação" : "Consistente"} />
        </div>
      </section>

      <section className="workspace-shortcuts" aria-label="Atalhos operacionais">
        <Link to="/atribuicoes"><strong>Atribuições</strong><span>Gerir carteiras e incluir processos em pauta</span></Link>
        <Link to="/entradas-saidas"><strong>Desempenho</strong><span>Acompanhar fluxo e produtividade diária</span></Link>
        <Link to="/servidores"><strong>Pessoas</strong><span>Comparar carga de trabalho e perfis</span></Link>
      </section>

      <section className="charts-grid">
        <BarChartCard title="Distribuição por setor" data={data?.por_setor || []} />
        <PieChartCard title="Composição por tipo" data={(data?.por_tipo || []).slice(0, 8)} />
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
