import { useEffect, useState } from "react";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";

const PAGE_SIZE = 50;

function DaysFlag({ days }) {
  if (days >= 30) return <span className="days-flag critical">● {days}d</span>;
  if (days >= 20) return <span className="days-flag alert">● {days}d</span>;
  if (days >= 10) return <span className="days-flag warning">● {days}d</span>;
  return <span className="days-flag ok">● {days}d</span>;
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`)
  );
}


export default function AttributionsPage() {
  const { filters, toQueryParams } = useFilters();
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const { data: response } = await api.get("/analytics/attributions", {
          params: { ...toQueryParams(), page, page_size: PAGE_SIZE },
        });
        if (!cancelled) setData(response);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Falha ao carregar atribuições.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [filters, page, retryCount]);

  if (loading) return <LoadingBlock label="Carregando atribuições..." />;
  if (error) return <ErrorBlock message={error} onRetry={() => setRetryCount((c) => c + 1)} />;

  const items = data?.items || [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Carteiras</p>
          <h1>Atribuições por processo</h1>
          <span>
            Referência: {data?.data_referencia || "Sem dados"} — processos ordenados pelo
            maior tempo com a mesma atribuição.
          </span>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Total de processos" value={total} />
        <StatCard label="Com atribuição" value={data?.total_com_atribuicao ?? 0} />
        <StatCard label="Sem atribuição" value={data?.total_sem_atribuicao ?? 0} />
        <StatCard
          label="Maior tempo registrado"
          value={`${data?.max_dias ?? 0}d`}
          hint={data?.max_dias >= 30 ? "Situação crítica" : data?.max_dias >= 20 ? "Alerta" : data?.max_dias >= 10 ? "Atenção" : "Normal"}
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Lista de processos e atribuições</h3>
            <p>
              <span className="days-flag ok" style={{ marginRight: 6 }}>● &lt;10d</span>
              <span className="days-flag warning" style={{ marginRight: 6 }}>● 10–19d</span>
              <span className="days-flag alert" style={{ marginRight: 6 }}>● 20–29d</span>
              <span className="days-flag critical">● 30d+</span>
            </p>
          </div>
        </div>

        <div className="table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Atribuição</th>
                <th>Protocolo</th>
                <th>Tipo</th>
                <th>Setor</th>
                <th>Desde</th>
                <th>Dias</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "var(--muted)", padding: "28px" }}>
                    Nenhum processo encontrado com os filtros atuais.
                  </td>
                </tr>
              ) : (
                items.map((item, idx) => (
                  <tr key={`${item.protocolo}-${item.setor}-${idx}`}>
                    <td>
                      {item.atribuicao ? (
                        <span style={{ fontWeight: 600 }}>{item.atribuicao}</span>
                      ) : (
                        <span style={{ color: "var(--muted)", fontStyle: "italic" }}>Sem atribuição</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{item.protocolo}</span>
                        {item.multiplos_setores && (
                          <span className="multi-sector-badge">⇄ múltiplos setores</span>
                        )}
                      </div>
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                      {item.tipo || "—"}
                    </td>
                    <td>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 10px",
                        borderRadius: 999,
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        background: "var(--primary-light)",
                        color: "var(--primary)",
                      }}>
                        {item.setor}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
                      {formatDate(item.entrada_atribuicao)}
                    </td>
                    <td>
                      <DaysFlag days={item.dias_com_atribuicao} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination-bar">
          <span className="pagination-summary">
            Página {page} de {totalPages} | {total} processos
          </span>
          <div className="table-actions">
            <button
              type="button"
              className="table-button"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Anterior
            </button>
            <button
              type="button"
              className="table-button"
              disabled={page === totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Próxima
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
