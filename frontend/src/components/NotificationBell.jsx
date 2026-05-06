import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import api from "../api/client";

function BellIcon({ active }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
      {active && <circle cx="19" cy="5" r="3" fill="#bf3535" stroke="none" />}
    </svg>
  );
}

function DaysBadge({ dias }) {
  const color =
    dias >= 90 ? "#4a148c" :
    dias >= 60 ? "#b71c1c" :
    dias >= 45 ? "#c0392b" :
    "#d4750e";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 999, fontSize: "0.7rem", fontWeight: 700,
      background: `${color}18`, color, whiteSpace: "nowrap",
    }}>
      {dias}d
    </span>
  );
}


export default function NotificationBell() {
  const navigate   = useNavigate();
  const [summary, setSummary] = useState(null);
  const [open, setOpen]       = useState(false);
  const dropdownRef = useRef(null);

  async function fetchSummary() {
    try {
      const { data } = await api.get("/alerts/summary");
      setSummary(data);
    } catch {
      // falha silenciosa — o sino fica sem badge
    }
  }

  useEffect(() => {
    fetchSummary();
    const interval = setInterval(fetchSummary, 10 * 60 * 1000); // a cada 10 min
    return () => clearInterval(interval);
  }, []);

  // Fecha ao clicar fora
  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const count    = summary?.total_badge ?? 0;
  const criticos = summary?.criticos    ?? [];

  return (
    <div ref={dropdownRef} style={{ position: "relative" }}>
      {/* Botão sino */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={count > 0 ? `${count} processo(s) sem movimentação ≥45 dias` : "Alertas críticos"}
        style={{
          appearance: "none",
          border: `1.5px solid ${count > 0 ? "rgba(191,53,53,0.3)" : "var(--border-strong)"}`,
          borderRadius: 999,
          padding: "7px 11px",
          cursor: "pointer",
          fontFamily: "inherit",
          background: count > 0 ? "rgba(191,53,53,0.07)" : "var(--primary-light)",
          color: count > 0 ? "var(--danger)" : "var(--muted)",
          display: "inline-flex",
          alignItems: "center",
          position: "relative",
          transition: "all 0.15s ease",
        }}
      >
        <BellIcon active={count > 0} />
        {count > 0 && (
          <span style={{
            position: "absolute", top: -5, right: -5,
            background: "var(--danger)", color: "#fff",
            borderRadius: 999, fontSize: "0.62rem", fontWeight: 800,
            padding: "1px 5px", minWidth: 17, textAlign: "center",
            border: "2px solid var(--bg)",
          }}>
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "calc(100% + 8px)",
          width: 360, background: "var(--panel)",
          border: "1px solid var(--border)", borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)", zIndex: 200, overflow: "hidden",
        }}>
          {/* Cabeçalho */}
          <div style={{
            padding: "12px 16px",
            borderBottom: "1px solid var(--border)",
            background: count > 0 ? "rgba(191,53,53,0.05)" : "var(--primary-light)",
          }}>
            <div style={{ fontWeight: 800, fontSize: "0.9rem", color: "var(--ink)", display: "flex", alignItems: "center", gap: 8 }}>
              <BellIcon active={count > 0} />
              Alertas de processos críticos
            </div>
            <div style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 4, display: "flex", gap: 12 }}>
              <span style={{ color: "#d4750e", fontWeight: 700 }}>{summary?.mais_de_30 ?? 0} &gt;30d</span>
              <span style={{ color: "#b71c1c", fontWeight: 700 }}>{summary?.mais_de_45 ?? 0} &gt;45d</span>
              <span style={{ color: "#4a148c", fontWeight: 700 }}>{summary?.mais_de_90 ?? 0} &gt;90d</span>
              {summary?.data_referencia && (
                <span style={{ marginLeft: "auto" }}>ref: {summary.data_referencia}</span>
              )}
            </div>
          </div>

          {/* Lista de processos */}
          {criticos.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--muted)", fontSize: "0.875rem" }}>
              Nenhum processo com ≥45 dias no momento
            </div>
          ) : (
            <>
              {criticos.map((p, i) => (
                <div key={i} style={{
                  padding: "9px 16px",
                  borderBottom: "1px solid var(--border)",
                  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
                }}>
                  <div style={{ minWidth: 0 }}>
                    <code style={{ fontSize: "0.78rem", color: "var(--primary)", fontWeight: 600, display: "block" }}>
                      {p.protocolo}
                    </code>
                    <span style={{ fontSize: "0.7rem", color: "var(--muted)" }}>
                      {p.setor} · {p.atribuicao || "Sem atribuição"}
                    </span>
                  </div>
                  <DaysBadge dias={p.dias_sem_movimentacao} />
                </div>
              ))}
              <div style={{ padding: "10px 16px", textAlign: "center" }}>
                <button
                  type="button"
                  onClick={() => { navigate("/atribuicoes"); setOpen(false); }}
                  style={{
                    appearance: "none", border: "none", background: "none",
                    color: "var(--accent)", fontWeight: 700, fontSize: "0.82rem",
                    cursor: "pointer",
                  }}
                >
                  Ver todos em Atribuições →
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
