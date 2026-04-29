import { useEffect, useState } from "react";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";

const PAGE_SIZE = 50;

const FAIXAS = [
  { label: "Todos",   min: null, max: null,  cls: null },
  { label: "< 15d",   min: null, max: 14,   cls: "ok" },
  { label: "15–29d",  min: 15,   max: 29,   cls: "warning" },
  { label: "30–44d",  min: 30,   max: 44,   cls: "alert" },
  { label: "45d+",    min: 45,   max: null,  cls: "critical" },
];

function DaysFlag({ days }) {
  if (days >= 45) return <span className="days-flag critical">● {days}d</span>;
  if (days >= 30) return <span className="days-flag alert">● {days}d</span>;
  if (days >= 15) return <span className="days-flag warning">● {days}d</span>;
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
  const [faixaIdx, setFaixaIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    setPage(1);
  }, [filters, faixaIdx]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const faixa = FAIXAS[faixaIdx];
        const params = {
          ...toQueryParams(),
          page,
          page_size: PAGE_SIZE,
          ...(faixa.min != null ? { min_dias: faixa.min } : {}),
          ...(faixa.max != null ? { max_dias: faixa.max } : {}),
        };
        const { data: response } = await api.get("/analytics/attributions", { params });
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
  }, [filters, page, faixaIdx, retryCount]);

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
        <StatCard label="Total de processos" value={data?.total ?? 0} />
        <StatCard label="Com atribuição" value={data?.total_com_atribuicao ?? 0} />
        <StatCard label="Sem atribuição" value={data?.total_sem_atribuicao ?? 0} />
        <StatCard
          label="Maior tempo registrado"
          value={`${data?.max_dias ?? 0}d`}
          hint={
            (data?.max_dias ?? 0) >= 45 ? "Situação crítica"
            : (data?.max_dias ?? 0) >= 30 ? "Alerta"
            : (data?.max_dias ?? 0) >= 15 ? "Atenção"
            : "Normal"
          }
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Lista de processos e atribuições</h3>
            <p>Filtre por faixa de tempo ou use os filtros do topo.</p>
          </div>
        </div>

        {/* Filtro por faixa de dias */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 18 }}>
          {FAIXAS.map((faixa, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setFaixaIdx(idx)}
              style={{
                appearance: "none",
                border: faixaIdx === idx
                  ? "2px solid transparent"
                  : "1.5px solid var(--border-strong)",
                borderRadius: 999,
                padding: "7px 16px",
                cursor: "pointer",
                fontFamily: "inherit",
                fontSize: "0.82rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.12s ease",
                ...(faixaIdx === idx && faixa.cls
                  ? {
                      background:
                        faixa.cls === "ok"       ? "rgba(26,122,80,0.12)"
                        : faixa.cls === "warning" ? "rgba(254,187,18,0.18)"
                        : faixa.cls === "alert"   ? "rgba(243,147,32,0.16)"
                        : "rgba(191,53,53,0.12)",
                      color:
                        faixa.cls === "ok"       ? "#1a7a50"
                        : faixa.cls === "warning" ? "#9a6c00"
                        : faixa.cls === "alert"   ? "#d4750e"
                        : "#bf3535",
                      borderColor: "transparent",
                    }
                  : faixaIdx === idx
                  ? {
                      background: "var(--primary)",
                      color: "#fff",
                      borderColor: "transparent",
                    }
                  : {
                      background: "transparent",
                      color: "var(--muted)",
                    }),
              }}
            >
              {faixa.cls && (
                <span style={{
                  width: 8, height: 8, borderRadius: "50%", display: "inline-block",
                  background:
                    faixa.cls === "ok"       ? "#1a7a50"
                    : faixa.cls === "warning" ? "#9a6c00"
                    : faixa.cls === "alert"   ? "#d4750e"
                    : "#bf3535",
                }} />
              )}
              {faixa.label}
              {faixaIdx === idx && total > 0 && (
                <span style={{
                  marginLeft: 2,
                  padding: "1px 7px",
                  borderRadius: 999,
                  fontSize: "0.7rem",
                  background: "rgba(0,0,0,0.08)",
                }}>
                  {total}
                </span>
              )}
            </button>
          ))}
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
