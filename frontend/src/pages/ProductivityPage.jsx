import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import PerformanceTabs from "../components/PerformanceTabs";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { formatUserNameAsInitials } from "../utils/userNameFormatter";


function formatDecimal(value, digits = 1) {
  return Number(value ?? 0).toFixed(digits);
}

const MEDALS = ["🥇", "🥈", "🥉"];
const MEDAL_STYLES = [
  { bg: "rgba(254,187,18,0.14)", border: "rgba(254,187,18,0.32)", color: "#7a5200" },
  { bg: "rgba(39,49,104,0.07)",  border: "rgba(39,49,104,0.16)",  color: "#3a4080" },
  { bg: "rgba(243,147,32,0.10)", border: "rgba(243,147,32,0.22)", color: "#d4750e" },
];

function ProdBar({ value }) {
  const pct = Math.min(100, Math.max(0, Number(value ?? 0)));
  const color = pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--accent)" : "var(--primary)";
  return (
    <div className="prod-bar-wrap">
      <div className="prod-bar-fill" style={{ width: `${pct}%`, background: color }} />
      <span className="prod-bar-label">{formatDecimal(value)}%</span>
    </div>
  );
}

const IcoProd = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);
const IcoIn = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
  </svg>
);
const IcoTrophy = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9H4.5a2.5 2.5 0 010-5H6"/><path d="M18 9h1.5a2.5 2.5 0 000-5H18"/>
    <path d="M4 22h16"/>
    <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/>
    <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/>
    <path d="M18 2H6v7a6 6 0 0012 0V2z"/>
  </svg>
);
const IcoCarga = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
  </svg>
);


export default function ProductivityPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/productivity",
    toQueryParams()
  );

  if (loading) return <div className="page-grid"><PerformanceTabs /><LoadingBlock label="Calculando produtividade por atribuição..." /></div>;
  if (error) return <div className="page-grid"><PerformanceTabs /><ErrorBlock message={error} onRetry={retry} /></div>;

  const maiorProdutor = data?.maior_produtor;
  const top3 = (data?.producao_por_atribuicao || []).slice(0, 3).filter(item => item.value > 0);

  return (
    <div className="page-grid">
      <PerformanceTabs />
      <section className="hero-panel ms-hero">
        <div className="ms-hero-body">
          <p className="eyebrow">Produtividade</p>
          <h1>Produção diária por atribuição</h1>
          <p className="ms-hero-sub">
            Comparação entre {data?.data_anterior || "a data anterior disponível"} e {data?.data_referencia || "a data de referência"}.
            {" "}{data?.criterio_produtividade}
          </p>
          {stale && <span className="stale-badge">Atualizando...</span>}
        </div>
        <div className="ms-hero-kpi">
          <span className="ms-hero-kpi-value">{data?.kpis?.total_produzido_dia ?? 0}</span>
          <span className="ms-hero-kpi-label">produzidos hoje</span>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard
          icon={<IcoProd />}
          label="Produção estimada do dia"
          value={data?.kpis?.total_produzido_dia ?? 0}
          hint="Processos resolvidos"
        />
        <StatCard
          icon={<IcoIn />}
          label="Entradas do dia"
          value={data?.kpis?.total_entradas_dia ?? 0}
          hint="Processos recebidos"
        />
        <StatCard
          icon={<IcoTrophy />}
          label="Maior produtor do dia"
          value={maiorProdutor ? `${maiorProdutor.produzidos} proc.` : "—"}
          hint={maiorProdutor?.atribuicao ? formatUserNameAsInitials(maiorProdutor.atribuicao) : undefined}
        />
        <StatCard
          icon={<IcoCarga />}
          label="Carga atual atribuída"
          value={data?.kpis?.carga_atual_total ?? 0}
          hint={`${data?.kpis?.atribuicoes_monitoradas ?? 0} atribuições monitoradas`}
        />
      </section>

      {top3.length > 0 && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Destaques do dia</h3>
              <p>Atribuições com maior volume de produção no snapshot atual.</p>
            </div>
          </div>
          <div className="top-producers-grid">
            {top3.map((item, i) => (
              <div
                key={item.label}
                className="producer-card"
                style={{ background: MEDAL_STYLES[i].bg, borderColor: MEDAL_STYLES[i].border }}
              >
                <span className="producer-medal">{MEDALS[i]}</span>
                <div className="producer-name" title={item.label}>
                  {formatUserNameAsInitials(item.label)}
                </div>
                <div className="producer-value" style={{ color: MEDAL_STYLES[i].color }}>
                  {item.value}<span className="producer-unit"> proc.</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="charts-grid">
        <BarChartCard
          title="Produção do dia por atribuição"
          subtitle="Processos que deixaram de estar na atribuição entre os dois snapshots."
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
            { key: "atribuicao",        label: "Atribuição" },
            { key: "carga_anterior",    label: "Carga ant." },
            { key: "carga_atual",       label: "Carga atual" },
            { key: "entradas",          label: "Entradas" },
            { key: "produzidos",        label: "Produzidos" },
            { key: "saldo",             label: "Saldo" },
            { key: "taxa_produtividade", label: "Taxa de produção", render: (v) => <ProdBar value={v} /> },
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
            { key: "atribuicao",           label: "Atribuição" },
            { key: "produzidos_periodo",   label: "Produzidos no período" },
            { key: "entradas_periodo",     label: "Entradas no período" },
            { key: "dias_com_movimento",   label: "Dias com movimento" },
            { key: "media_diaria_producao", label: "Média diária", render: (v) => formatDecimal(v, 2) },
          ]}
          rows={data?.ranking_producao_periodo || []}
          emptyMessage="Ainda não há período suficiente para montar o ranking acumulado."
        />
      </section>
    </div>
  );
}
