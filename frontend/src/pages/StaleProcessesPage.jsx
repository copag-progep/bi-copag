import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";

const PAGE_SIZE = 50;


export default function StaleProcessesPage() {
  const { filters, toQueryParams } = useFilters();
  const [data, setData] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await api.get("/analytics/stale", { params: toQueryParams() });
        setData(response.data);
      } catch (requestError) {
        setError(requestError.response?.data?.detail || "Falha ao carregar alertas.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [filters]);

  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  if (loading) {
    return <LoadingBlock label="Verificando processos parados..." />;
  }

  if (error) {
    return <div className="alert error">{error}</div>;
  }

  const processes = data?.processos || [];
  const totalPages = Math.max(Math.ceil(processes.length / PAGE_SIZE), 1);
  const paginatedProcesses = processes.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Alertas críticos</p>
          <h1>Processos sem movimentação</h1>
          <span>Data de referência: {data?.data_referencia || "Sem dados"}.</span>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Mais de 10 dias" value={data?.contagens?.mais_de_10 ?? 0} />
        <StatCard label="Mais de 20 dias" value={data?.contagens?.mais_de_20 ?? 0} />
        <StatCard label="Mais de 30 dias" value={data?.contagens?.mais_de_30 ?? 0} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Painel de processos críticos</h3>
            <p>Processos com maior tempo sem movimentação inferida no setor atual.</p>
          </div>
        </div>
        <DataTable
          columns={[
            { key: "protocolo", label: "Protocolo" },
            { key: "setor", label: "Setor" },
            { key: "atribuicao", label: "Atribuição" },
            { key: "tipo", label: "Tipo" },
            { key: "entrada_setor", label: "Entrada no setor" },
            { key: "dias_sem_movimentacao", label: "Dias sem movimentação" },
          ]}
          rows={paginatedProcesses}
          emptyMessage="Nenhum processo crítico encontrado com os filtros atuais."
        />
        <div className="pagination-bar">
          <span className="pagination-summary">
            Pagina {currentPage} de {totalPages} | {processes.length} processos
          </span>
          <div className="table-actions">
            <button
              type="button"
              className="table-button"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            >
              Anterior
            </button>
            <button
              type="button"
              className="table-button"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            >
              Proxima
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
