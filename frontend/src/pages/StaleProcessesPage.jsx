import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";


export default function StaleProcessesPage() {
  const { filters, toQueryParams } = useFilters();
  const [data, setData] = useState(null);
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

  if (loading) {
    return <LoadingBlock label="Verificando processos parados..." />;
  }

  if (error) {
    return <div className="alert error">{error}</div>;
  }

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
          rows={data?.processos || []}
          emptyMessage="Nenhum processo crítico encontrado com os filtros atuais."
        />
      </section>
    </div>
  );
}
