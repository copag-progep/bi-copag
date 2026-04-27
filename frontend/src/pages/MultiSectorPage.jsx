import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import { useFilters } from "../context/FiltersContext";
import { useAnalyticsData } from "../hooks/useAnalyticsData";


export default function MultiSectorPage() {
  const { toQueryParams } = useFilters();
  const { data, loading, stale, error, retry } = useAnalyticsData(
    "/analytics/multi-sector",
    toQueryParams()
  );

  if (loading) return <LoadingBlock label="Investigando múltiplos setores..." />;
  if (error) return <ErrorBlock message={error} onRetry={retry} />;

  const totalOcorrencias = data?.processos?.length ?? 0;

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Consistência do snapshot</p>
          <h1>Processos em múltiplos setores</h1>
          <span>Protocolos que aparecem em mais de um setor no mesmo dia.</span>
          <div className="hero-badge">
            <strong>{totalOcorrencias}</strong>
            <span>{totalOcorrencias === 1 ? "ocorrência encontrada" : "ocorrências encontradas"}</span>
          </div>
          {stale ? <span className="stale-badge">Atualizando...</span> : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Ocorrências para {data?.data_referencia || "a data selecionada"}</h3>
            <p>Use o filtro de data no topo para analisar snapshots específicos.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "protocolo", label: "Protocolo" },
            { key: "setores", label: "Setores" },
            { key: "data_relatorio", label: "Data do relatório" },
          ]}
          rows={data?.processos || []}
          emptyMessage="Nenhum processo encontrado em múltiplos setores com os filtros atuais."
        />
      </section>
    </div>
  );
}
