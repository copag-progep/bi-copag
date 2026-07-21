import { useEffect, useMemo, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import PerformanceTabs from "../components/PerformanceTabs";
import { useFilters } from "../context/FiltersContext";


function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function FlowBadge({ value }) {
  const entrada = value === "entrada";
  return (
    <span className={`flow-detail-badge ${entrada ? "entry" : "exit"}`}>
      <span aria-hidden="true">{entrada ? "↑" : "↓"}</span>
      {entrada ? "Entrada" : "Saída"}
    </span>
  );
}


export default function FlowDetailsPage() {
  const { filters } = useFilters();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [fluxo, setFluxo] = useState("todos");
  const [buscaInput, setBuscaInput] = useState("");
  const [buscaParam, setBuscaParam] = useState("");
  const [sort, setSort] = useState({ key: "fluxo", dir: "asc" });
  const [page, setPage] = useState(1);

  const queryParams = useMemo(() => ({
    ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)),
    fluxo,
    protocolo_busca: buscaParam || undefined,
    sort_by: sort.key,
    sort_dir: sort.dir,
    page,
    page_size: 50,
  }), [filters, fluxo, buscaParam, sort, page]);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api.get("/analytics/flow-details", { params: queryParams, timeout: 90000 })
      .then(({ data: response }) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || "Não foi possível carregar as movimentações.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [queryParams, retryCount]);

  function changeFlow(next) {
    setFluxo(next);
    setPage(1);
  }

  function handleSearch(event) {
    event.preventDefault();
    setBuscaParam(buscaInput.trim());
    setPage(1);
  }

  function clearSearch() {
    setBuscaInput("");
    setBuscaParam("");
    setPage(1);
  }

  function handleSort(key) {
    setSort((current) => current.key === key
      ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
      : { key, dir: "asc" });
    setPage(1);
  }

  const columns = [
    { key: "protocolo", label: "Protocolo", sortable: true, render: (value) => <strong className="flow-protocol">{value}</strong> },
    { key: "atribuicao", label: "Atribuição", sortable: true },
    { key: "tipo", label: "Tipo de processo", sortable: true },
    { key: "setor", label: "Setor", sortable: true, render: (value) => <span className="sector-tag">{value}</span> },
    { key: "fluxo", label: "Fluxo", sortable: true, render: (value) => <FlowBadge value={value} /> },
  ];

  return (
    <div className="page-grid">
      <PerformanceTabs />

      {loading && !data ? <LoadingBlock label="Identificando processos que entraram e saíram..." /> : null}
      {error && !data ? <ErrorBlock message={error} onRetry={() => setRetryCount((value) => value + 1)} /> : null}

      {data ? (
        <>
          <section className="hero-panel flow-hero flow-detail-hero">
            <div className="ms-hero-body">
              <p className="eyebrow">Detalhamento do fluxo</p>
              <h1>Movimentações por processo</h1>
              <div className="flow-hero-dates">
                <span className="flow-date-from">{formatDate(data.data_anterior)}</span>
                <span className="flow-arrow" aria-hidden="true">→</span>
                <span className="flow-date-to">{formatDate(data.data_referencia)}</span>
              </div>
            </div>
            <div className="flow-hero-metrics">
              <div className="flow-metric-item flow-metric-in">
                <span className="flow-metric-val">+{data.total_entradas}</span>
                <span className="flow-metric-lbl">entradas</span>
              </div>
              <div className="flow-metric-sep" />
              <div className="flow-metric-item flow-metric-out">
                <span className="flow-metric-val">−{data.total_saidas}</span>
                <span className="flow-metric-lbl">saídas</span>
              </div>
            </div>
          </section>

          {!data.comparacao_disponivel ? (
            <section className="flow-comparison-notice neutral" role="status">
              <strong>Comparação ainda indisponível</strong>
              <span>Não há snapshot anterior para comparar com {formatDate(data.data_referencia)}. As movimentações serão identificadas após uma nova atualização.</span>
            </section>
          ) : null}

          {data.setores_sem_base_anterior?.length ? (
            <section className="flow-comparison-notice warning" role="status">
              <strong>Base anterior incompleta</strong>
              <span>
                {data.setores_sem_base_anterior.join(", ")} não possui snapshot na data anterior. Os registros atuais desses setores são tratados como entradas de base.
              </span>
            </section>
          ) : null}

          {data.comparacao_disponivel ? (
            <section className="panel flow-detail-panel">
              <div className="panel-header flow-detail-header">
                <div>
                  <h3>Processos movimentados</h3>
                  <p>Entradas e saídas inferidas pela comparação dos dois snapshots.</p>
                </div>
                <div className="flow-detail-segments" aria-label="Filtrar por fluxo">
                  <button type="button" className={fluxo === "todos" ? "active" : ""} onClick={() => changeFlow("todos")}>Todos <span>{data.total_entradas + data.total_saidas}</span></button>
                  <button type="button" className={fluxo === "entrada" ? "active" : ""} onClick={() => changeFlow("entrada")}>Entradas <span>{data.total_entradas}</span></button>
                  <button type="button" className={fluxo === "saida" ? "active" : ""} onClick={() => changeFlow("saida")}>Saídas <span>{data.total_saidas}</span></button>
                </div>
              </div>

              <form className="flow-detail-search" onSubmit={handleSearch}>
                <input
                  type="text"
                  value={buscaInput}
                  onChange={(event) => setBuscaInput(event.target.value)}
                  placeholder="Buscar por número de processo (protocolo)..."
                  aria-label="Buscar protocolo nas movimentações"
                />
                <button type="submit" className="primary-button">Buscar</button>
                {buscaParam ? <button type="button" className="ghost-button" onClick={clearSearch}>Limpar</button> : null}
              </form>

              {error ? <div className="alert error">{error}</div> : null}
              {loading ? <LoadingBlock label="Atualizando movimentações..." /> : (
                <DataTable
                  columns={columns}
                  rows={data.items}
                  emptyMessage="Nenhum processo movimentado com os filtros atuais."
                  sortKey={sort.key}
                  sortDir={sort.dir}
                  onSort={handleSort}
                  rowKey={(row) => `${row.protocolo}|${row.setor}|${row.fluxo}`}
                />
              )}

              <div className="pagination-bar">
                <span className="pagination-summary">
                  {data.total} resultado{data.total !== 1 ? "s" : ""} · página {data.page} de {data.total_pages}
                </span>
                <div className="table-actions">
                  <button type="button" className="table-button" disabled={data.page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>Anterior</button>
                  <button type="button" className="table-button" disabled={data.page >= data.total_pages || loading} onClick={() => setPage((value) => value + 1)}>Próxima</button>
                </div>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
