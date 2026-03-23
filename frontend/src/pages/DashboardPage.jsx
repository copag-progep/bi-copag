import { useEffect, useState } from "react";

import api from "../api/client";
import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import PieChartCard from "../charts/PieChartCard";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";


export default function DashboardPage() {
  const { filters, toQueryParams } = useFilters();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await api.get("/analytics/dashboard", { params: toQueryParams() });
        setData(response.data);
      } catch (requestError) {
        setError(requestError.response?.data?.detail || "Falha ao carregar dashboard.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [filters]);

  if (loading) {
    return <LoadingBlock label="Montando dashboard principal..." />;
  }

  if (error) {
    return <div className="alert error">{error}</div>;
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Dashboard principal</p>
          <h1>Visão executiva da tramitação</h1>
          <span>Data de referência: {data?.data_referencia || "Sem snapshots importados"}</span>
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
        <BarChartCard title="Ranking de atribuições" data={(data?.ranking_atribuicoes || []).slice(0, 10)} color="#c2603b" />
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
