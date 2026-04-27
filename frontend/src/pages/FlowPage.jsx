import { useEffect, useState } from "react";

import api from "../api/client";
import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import DataTable from "../components/DataTable";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";


export default function FlowPage() {
  const { filters, toQueryParams } = useFilters();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await api.get("/analytics/entries-exits", { params: toQueryParams() });
        setData(response.data);
      } catch (requestError) {
        setError(requestError.response?.data?.detail || "Falha ao carregar métricas de entradas e saídas.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [filters, retryCount]);

  if (loading) {
    return <LoadingBlock label="Calculando entradas e saídas..." />;
  }

  if (error) {
    return <ErrorBlock message={error} onRetry={() => setRetryCount((c) => c + 1)} />;
  }

  const totalEntradas = (data?.resumo_setorial || []).reduce((accumulator, item) => accumulator + item.entradas, 0);
  const totalSaidas = (data?.resumo_setorial || []).reduce((accumulator, item) => accumulator + item.saidas, 0);
  const totalSaldo = (data?.resumo_setorial || []).reduce((accumulator, item) => accumulator + item.saldo, 0);

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Entradas e saídas</p>
          <h1>Fluxo diário por setor</h1>
          <span>
            Comparação entre {data?.data_anterior || "a data anterior disponível"} e {data?.data_referencia || "a data de referência"}.
          </span>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Entradas do dia" value={totalEntradas} />
        <StatCard label="Saídas do dia" value={totalSaidas} />
        <StatCard label="Saldo do dia" value={totalSaldo} />
      </section>

      <section className="charts-grid">
        <BarChartCard title="Entradas por setor" data={data?.entradas_por_setor || []} />
        <BarChartCard title="Saídas por setor" data={data?.saidas_por_setor || []} color="#f39320" />
        <BarChartCard title="Saldo por setor" data={data?.saldo_por_setor || []} color="#273168" />
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
            { key: "saldo", label: "Saldo" },
            { key: "carga_atual", label: "Carga atual" },
          ]}
          rows={data?.resumo_setorial || []}
        />
      </section>
    </div>
  );
}
