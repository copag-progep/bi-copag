import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { formatUserNameAsInitials } from "../utils/userNameFormatter";


function formatDecimal(value, digits = 1) {
  return Number(value ?? 0).toFixed(digits);
}


export default function ProductivityPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/productivity",
    toQueryParams()
  );

  if (loading) return <LoadingBlock label="Calculando produtividade por atribuição..." />;
  if (error) return <ErrorBlock message={error} onRetry={retry} />;

  const maiorProdutor = data?.maior_produtor;

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Produtividade</p>
          <h1>Produção diária por atribuição</h1>
          <span>
            Comparação entre {data?.data_anterior || "a data anterior disponível"} e {data?.data_referencia || "a data de referência"}.
            {" "}{data?.criterio_produtividade}
          </span>
          {stale ? <span className="stale-badge">Atualizando...</span> : null}
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Produção estimada do dia" value={data?.kpis?.total_produzido_dia ?? 0} />
        <StatCard label="Entradas do dia" value={data?.kpis?.total_entradas_dia ?? 0} />
        <StatCard
          label="Maior produtor do dia"
          value={maiorProdutor ? `${maiorProdutor.produzidos} processos` : "0 processos"}
          hint={maiorProdutor?.atribuicao}
        />
        <StatCard
          label="Carga atual atribuída"
          value={data?.kpis?.carga_atual_total ?? 0}
          hint={`${data?.kpis?.atribuicoes_monitoradas ?? 0} atribuições monitoradas`}
        />
      </section>

      <section className="charts-grid">
        <BarChartCard
          title="Produção do dia por atribuição"
          subtitle="Processos que deixaram de estar na atribuição entre o snapshot anterior e o atual."
          data={data?.producao_por_atribuicao || []}
          tickFormatter={formatUserNameAsInitials}
        />
        <BarChartCard
          title="Entradas do dia por atribuição"
          subtitle="Processos que passaram a constar na atribuição na data de referência."
          data={data?.entradas_por_atribuicao || []}
          color="#f39320"
          tickFormatter={formatUserNameAsInitials}
        />
        <BarChartCard
          title="Carga atual por atribuição"
          subtitle="Quantidade de processos hoje em cada carteira."
          data={data?.carga_atual_por_atribuicao || []}
          color="#273168"
          tickFormatter={formatUserNameAsInitials}
        />
        <LineChartCard
          title="Evolução diária da produção por atribuição"
          subtitle="Série das atribuições mais produtivas no período filtrado."
          data={data?.evolucao_produtividade || []}
          xKey="date"
          valueKey="produzidos"
          seriesKey="atribuicao"
          formatSeriesName={formatUserNameAsInitials}
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Resumo do dia por atribuição</h3>
            <p>Leitura diária da produtividade estimada por usuário a partir da comparação entre snapshots.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "atribuicao", label: "Atribuição" },
            { key: "carga_anterior", label: "Carga anterior" },
            { key: "carga_atual", label: "Carga atual" },
            { key: "entradas", label: "Entradas" },
            { key: "produzidos", label: "Produzidos" },
            { key: "saldo", label: "Saldo" },
            { key: "taxa_produtividade", label: "Taxa de produção", render: (v) => `${formatDecimal(v)}%` },
          ]}
          rows={data?.resumo_atribuicoes || []}
          emptyMessage="Não há histórico suficiente para calcular produtividade por atribuição."
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Ranking acumulado no período</h3>
            <p>Total estimado de produção por atribuição dentro do recorte filtrado.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "atribuicao", label: "Atribuição" },
            { key: "produzidos_periodo", label: "Produzidos no período" },
            { key: "entradas_periodo", label: "Entradas no período" },
            { key: "dias_com_movimento", label: "Dias com movimento" },
            { key: "media_diaria_producao", label: "Média diária", render: (v) => formatDecimal(v, 2) },
          ]}
          rows={data?.ranking_producao_periodo || []}
          emptyMessage="Ainda não há período suficiente para montar o ranking acumulado."
        />
      </section>
    </div>
  );
}
