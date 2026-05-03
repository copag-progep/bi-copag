import { useEffect, useRef, useState } from "react";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";
import { generateAttributionsPdf } from "../utils/attributionsPdf";

const PAGE_SIZE = 50;

const FAIXAS = [
  { label: "Todos",   min: null, max: null,  cls: null },
  { label: "< 15d",   min: null, max: 14,   cls: "ok" },
  { label: "15–29d",  min: 15,   max: 29,   cls: "warning" },
  { label: "30–44d",  min: 30,   max: 44,   cls: "alert" },
  { label: "45–59d",  min: 45,   max: 59,   cls: "serious" },
  { label: "60–89d",  min: 60,   max: 89,   cls: "critical" },
  { label: "90d+",    min: 90,   max: null,  cls: "extreme" },
];

const FLAG_COLORS = {
  ok:       { dot: "#1a7a50", bg: "rgba(26,122,80,0.12)",    text: "#1a7a50" },
  warning:  { dot: "#9a6c00", bg: "rgba(254,187,18,0.18)",   text: "#9a6c00" },
  alert:    { dot: "#d4750e", bg: "rgba(243,147,32,0.16)",   text: "#d4750e" },
  serious:  { dot: "#c0392b", bg: "rgba(192,57,43,0.13)",    text: "#c0392b" },
  critical: { dot: "#b71c1c", bg: "rgba(183,28,28,0.13)",    text: "#b71c1c" },
  extreme:  { dot: "#4a148c", bg: "rgba(74,20,140,0.12)",    text: "#4a148c" },
};

function DaysFlag({ days }) {
  if (days >= 90) return <span className="days-flag extreme">● {days}d</span>;
  if (days >= 60) return <span className="days-flag critical">● {days}d</span>;
  if (days >= 45) return <span className="days-flag serious">● {days}d</span>;
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

function SortIcon({ col, sortBy, sortDir }) {
  if (sortBy !== col) return <span style={{ opacity: 0.3, marginLeft: 4, fontSize: "0.75em" }}>↕</span>;
  return (
    <span style={{ marginLeft: 4, fontSize: "0.75em", color: "var(--accent)" }}>
      {sortDir === "asc" ? "↑" : "↓"}
    </span>
  );
}


export default function AttributionsPage() {
  const { filters, toQueryParams } = useFilters();

  const [data, setData]             = useState(null);
  const [page, setPage]             = useState(1);
  const [faixaIdx, setFaixaIdx]     = useState(0);
  const [semAtribuicao, setSemAtribuicao] = useState(false);
  const [sortBy, setSortBy]         = useState("dias");
  const [sortDir, setSortDir]       = useState("desc");
  const [buscaInput, setBuscaInput] = useState("");
  const [buscaParam, setBuscaParam] = useState("");
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [pdfLoading, setPdfLoading] = useState(false);

  const buscaRef = useRef(null);

  // Reset page quando qualquer filtro/ordenação muda
  useEffect(() => {
    setPage(1);
  }, [filters, faixaIdx, semAtribuicao, sortBy, sortDir, buscaParam]);

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
          sort_by: sortBy,
          sort_dir: sortDir,
          ...(faixa.min != null  ? { min_dias: faixa.min }        : {}),
          ...(faixa.max != null  ? { max_dias: faixa.max }        : {}),
          ...(semAtribuicao      ? { sem_atribuicao: true }       : {}),
          ...(buscaParam         ? { protocolo_busca: buscaParam } : {}),
        };
        const { data: response } = await api.get("/analytics/attributions", { params, timeout: 60000 });
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
  }, [filters, page, faixaIdx, semAtribuicao, sortBy, sortDir, buscaParam, retryCount]);

  function handleSort(col) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
  }

  function buildFiltersText() {
    const parts = [];
    if (filters.setor)      parts.push(`Setor: ${filters.setor}`);
    if (filters.tipo)       parts.push(`Tipo: ${filters.tipo}`);
    if (filters.atribuicao) parts.push(`Atribuição: ${filters.atribuicao}`);
    const faixa = FAIXAS[faixaIdx];
    if (faixa.label !== "Todos") parts.push(`Faixa: ${faixa.label}`);
    if (semAtribuicao)      parts.push("Sem atribuição");
    if (buscaParam)         parts.push(`Protocolo: "${buscaParam}"`);
    if (sortBy !== "dias")  parts.push(`Ordem: ${sortBy} ${sortDir === "asc" ? "↑" : "↓"}`);
    return parts.length ? parts.join("  ·  ") : null;
  }

  async function handleGeneratePdf() {
    setPdfLoading(true);
    try {
      const faixa = FAIXAS[faixaIdx];
      const params = {
        ...toQueryParams(),
        page: 1,
        page_size: 5000,
        sort_by: sortBy,
        sort_dir: sortDir,
        ...(faixa.min != null  ? { min_dias: faixa.min }        : {}),
        ...(faixa.max != null  ? { max_dias: faixa.max }        : {}),
        ...(semAtribuicao      ? { sem_atribuicao: true }       : {}),
        ...(buscaParam         ? { protocolo_busca: buscaParam } : {}),
      };
      const { data: pdfData } = await api.get("/analytics/attributions", { params, timeout: 120000 });
      generateAttributionsPdf({
        items:          pdfData.items,
        stats: {
          total:      pdfData.total,
          totalCom:   pdfData.total_com_atribuicao,
          totalSem:   pdfData.total_sem_atribuicao,
          maxDias:    pdfData.max_dias,
        },
        dataReferencia: pdfData.data_referencia,
        filtersText:    buildFiltersText(),
      });
    } catch (err) {
      console.error("Erro ao gerar PDF:", err);
    } finally {
      setPdfLoading(false);
    }
  }

  function handleBuscaSubmit(e) {
    e.preventDefault();
    setBuscaParam(buscaInput.trim());
  }

  function handleBuscaLimpar() {
    setBuscaInput("");
    setBuscaParam("");
    buscaRef.current?.focus();
  }

  if (loading) return <LoadingBlock label="Carregando atribuições..." />;
  if (error)   return <ErrorBlock message={error} onRetry={() => setRetryCount((c) => c + 1)} />;

  const items      = data?.items || [];
  const total      = data?.total ?? 0;
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
          hint={
            (data?.max_dias ?? 0) >= 90 ? "Situação extrema"
            : (data?.max_dias ?? 0) >= 60 ? "Crítico"
            : (data?.max_dias ?? 0) >= 45 ? "Grave"
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
            <p>Filtre por faixa de tempo, atribuição ou busque um protocolo específico.</p>
          </div>
          <button
            type="button"
            onClick={handleGeneratePdf}
            disabled={pdfLoading || total === 0}
            style={{
              appearance: "none",
              border: "none",
              borderRadius: "var(--radius)",
              padding: "10px 18px",
              cursor: pdfLoading || total === 0 ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              fontSize: "0.875rem",
              fontWeight: 700,
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: pdfLoading || total === 0
                ? "rgba(39,49,104,0.08)"
                : "linear-gradient(135deg, #273168, #1c2350)",
              color: pdfLoading || total === 0 ? "var(--muted)" : "#fff",
              boxShadow: pdfLoading || total === 0 ? "none" : "0 3px 10px rgba(39,49,104,0.25)",
              transition: "all 0.15s ease",
              opacity: pdfLoading || total === 0 ? 0.6 : 1,
              whiteSpace: "nowrap",
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="12" y1="18" x2="12" y2="12"/>
              <line x1="9" y1="15" x2="15" y2="15"/>
            </svg>
            {pdfLoading ? "Gerando PDF..." : "Gerar PDF"}
          </button>
        </div>

        {/* Linha 1: filtros de faixa + toggle sem atribuição */}
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginBottom: 10 }}>
          {FAIXAS.map((faixa, idx) => {
            const active = faixaIdx === idx;
            const colors = faixa.cls ? FLAG_COLORS[faixa.cls] : null;
            return (
              <button
                key={idx}
                type="button"
                onClick={() => setFaixaIdx(idx)}
                style={{
                  appearance: "none",
                  border: active ? "2px solid transparent" : "1.5px solid var(--border-strong)",
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
                  background: active && colors ? colors.bg : active ? "var(--primary)" : "transparent",
                  color: active && colors ? colors.text : active ? "#fff" : "var(--muted)",
                }}
              >
                {colors && (
                  <span style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: colors.dot }} />
                )}
                {faixa.label}
                {active && total > 0 && (
                  <span style={{ marginLeft: 2, padding: "1px 7px", borderRadius: 999, fontSize: "0.7rem", background: "rgba(0,0,0,0.08)" }}>
                    {total}
                  </span>
                )}
              </button>
            );
          })}

          {/* Separador visual */}
          <span style={{ width: 1, height: 24, background: "var(--border-strong)", margin: "0 4px" }} />

          {/* Toggle: Sem atribuição */}
          <button
            type="button"
            onClick={() => setSemAtribuicao((v) => !v)}
            style={{
              appearance: "none",
              border: semAtribuicao ? "2px solid transparent" : "1.5px solid var(--border-strong)",
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
              background: semAtribuicao ? "rgba(39,49,104,0.1)" : "transparent",
              color: semAtribuicao ? "var(--primary)" : "var(--muted)",
            }}
          >
            Sem atribuição
            {semAtribuicao && total > 0 && (
              <span style={{ marginLeft: 2, padding: "1px 7px", borderRadius: 999, fontSize: "0.7rem", background: "rgba(0,0,0,0.08)" }}>
                {total}
              </span>
            )}
          </button>
        </div>

        {/* Linha 2: busca por protocolo */}
        <form onSubmit={handleBuscaSubmit} style={{ display: "flex", gap: 8, marginBottom: 18 }}>
          <input
            ref={buscaRef}
            type="text"
            value={buscaInput}
            onChange={(e) => setBuscaInput(e.target.value)}
            placeholder="Buscar por número de processo (protocolo)..."
            style={{
              flex: 1,
              border: "1.5px solid var(--border-strong)",
              borderRadius: "var(--radius)",
              padding: "10px 14px",
              fontSize: "0.875rem",
              fontFamily: "inherit",
              color: "var(--ink)",
              background: "#fafbff",
              outline: "none",
            }}
          />
          <button type="submit" className="primary-button" style={{ padding: "10px 18px", fontSize: "0.875rem" }}>
            Buscar
          </button>
          {buscaParam && (
            <button
              type="button"
              className="ghost-button"
              onClick={handleBuscaLimpar}
              style={{ padding: "10px 16px", fontSize: "0.875rem" }}
            >
              Limpar
            </button>
          )}
        </form>

        {buscaParam && (
          <div style={{ marginBottom: 12, fontSize: "0.82rem", color: "var(--muted)" }}>
            Buscando por: <strong style={{ color: "var(--ink)" }}>{buscaParam}</strong>
            {" "}— {total} resultado{total !== 1 ? "s" : ""}
          </div>
        )}

        <div className="table-shell">
          <table className="data-table">
            <thead>
              <tr>
                {/* Cabeçalho ordenável: Atribuição */}
                <th
                  style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                  onClick={() => handleSort("atribuicao")}
                  title="Ordenar por atribuição"
                >
                  Atribuição <SortIcon col="atribuicao" sortBy={sortBy} sortDir={sortDir} />
                </th>
                <th>Protocolo</th>
                {/* Cabeçalho ordenável: Tipo */}
                <th
                  style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                  onClick={() => handleSort("tipo")}
                  title="Ordenar por tipo"
                >
                  Tipo <SortIcon col="tipo" sortBy={sortBy} sortDir={sortDir} />
                </th>
                <th>Setor</th>
                <th>Desde</th>
                <th
                  style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                  onClick={() => handleSort("dias")}
                  title="Ordenar por dias"
                >
                  Dias <SortIcon col="dias" sortBy={sortBy} sortDir={sortDir} />
                </th>
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
                        display: "inline-block", padding: "2px 10px", borderRadius: 999,
                        fontSize: "0.72rem", fontWeight: 700,
                        background: "var(--primary-light)", color: "var(--primary)",
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
