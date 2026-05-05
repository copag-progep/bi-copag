import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";


function fmtDate(val) {
  if (!val) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
      new Date(`${val}T00:00:00Z`)
    );
  } catch {
    return val;
  }
}

function calcDias(entrada, saida) {
  if (!entrada) return 0;
  const end   = saida ? new Date(`${saida}T00:00:00Z`) : new Date();
  const start = new Date(`${entrada}T00:00:00Z`);
  return Math.max(0, Math.round((end - start) / 86400000));
}


function ProcessCard({ proc }) {
  return (
    <section className="panel">
      {/* Cabeçalho do processo */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        <div>
          <code style={{
            fontSize: "1rem", fontWeight: 700, color: "var(--primary)",
            background: "var(--primary-light)", padding: "4px 14px",
            borderRadius: "var(--radius)", fontFamily: "courier, monospace",
            letterSpacing: "0.04em",
          }}>
            {proc.protocolo}
          </code>
          {proc.tipo && (
            <p style={{ margin: "8px 0 0", color: "var(--muted)", fontSize: "0.875rem" }}>
              {proc.tipo}
            </p>
          )}
        </div>
        <span style={{
          padding: "5px 14px", borderRadius: 999, fontSize: "0.78rem", fontWeight: 700,
          background: "var(--primary-light)", color: "var(--primary)", whiteSpace: "nowrap",
        }}>
          {proc.setor_atual}
        </span>
      </div>

      {/* Estado atual */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12,
        padding: "14px 16px", borderRadius: "var(--radius)",
        background: "var(--primary-light)", marginBottom: 22,
      }}>
        {[
          { label: "Atribuição atual",  value: proc.atribuicao_atual || "Sem atribuição", muted: !proc.atribuicao_atual },
          { label: "Primeira aparição", value: fmtDate(proc.data_primeira) },
          { label: "Última aparição",   value: fmtDate(proc.data_ultima) },
        ].map(({ label, value, muted }) => (
          <div key={label}>
            <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--muted)",
              textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 5 }}>
              {label}
            </div>
            <div style={{ fontWeight: 600, color: muted ? "var(--muted)" : "var(--ink)",
              fontStyle: muted ? "italic" : "normal", fontSize: "0.875rem" }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Histórico */}
      {proc.historico.length > 0 && (
        <>
          <div className="panel-header" style={{ marginBottom: 10 }}>
            <div>
              <h3>Histórico de movimentações</h3>
              <p>Períodos inferidos a partir dos snapshots diários do SEI.</p>
            </div>
          </div>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Setor</th>
                  <th>Atribuição</th>
                  <th>Tipo</th>
                  <th>Entrada</th>
                  <th>Saída</th>
                  <th>Duração</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {proc.historico.map((span, i) => {
                  const dias = calcDias(span.data_entrada, span.data_saida);
                  return (
                    <tr key={i}>
                      <td>
                        <span style={{
                          padding: "2px 10px", borderRadius: 999, fontSize: "0.72rem",
                          fontWeight: 700, background: "var(--primary-light)", color: "var(--primary)",
                        }}>
                          {span.setor}
                        </span>
                      </td>
                      <td style={{ fontWeight: span.ativa ? 600 : 400 }}>
                        {span.atribuicao || (
                          <span style={{ color: "var(--muted)", fontStyle: "italic" }}>Sem atribuição</span>
                        )}
                      </td>
                      <td style={{ fontSize: "0.82rem", color: "var(--muted)" }}>{span.tipo}</td>
                      <td style={{ fontSize: "0.82rem", whiteSpace: "nowrap" }}>{fmtDate(span.data_entrada)}</td>
                      <td style={{ fontSize: "0.82rem", whiteSpace: "nowrap" }}>
                        {span.ativa ? "—" : fmtDate(span.data_saida)}
                      </td>
                      <td>
                        <span style={{
                          padding: "2px 10px", borderRadius: 999, fontSize: "0.78rem", fontWeight: 700,
                          background: span.ativa ? "var(--accent-light)" : "var(--primary-light)",
                          color: span.ativa ? "var(--accent-dark)" : "var(--primary)",
                        }}>
                          {dias}d
                        </span>
                      </td>
                      <td>
                        {span.ativa ? (
                          <span style={{
                            padding: "2px 10px", borderRadius: 999, fontSize: "0.72rem", fontWeight: 700,
                            background: "rgba(26,122,80,0.1)", color: "var(--success)",
                          }}>
                            Ativo
                          </span>
                        ) : (
                          <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>Encerrado</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}


export default function ProcessSearchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const q = searchParams.get("q") || "";
  const [inputValue, setInputValue] = useState(q);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setInputValue(q);
    if (!q) { setData(null); return; }

    let cancelled = false;
    setLoading(true);
    setError("");

    api.get("/processes/search", { params: { q } })
      .then(({ data: result }) => { if (!cancelled) setData(result); })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "Falha na busca."); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [q]);

  function handleSearch(e) {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) navigate(`/busca?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Busca global</p>
          <h1>Localizar processo</h1>
          <span>
            Busque pelo número de protocolo para ver onde ele está e por onde passou
            desde o primeiro snapshot importado.
          </span>
        </div>
      </section>

      <section className="panel">
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 10 }}>
          <div style={{ position: "relative", flex: 1 }}>
            <svg
              style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)",
                opacity: 0.35, pointerEvents: "none" }}
              width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ex.: 23067.001197/2025-91 ou parte do número..."
              style={{
                width: "100%", border: "1.5px solid var(--border-strong)",
                borderRadius: "var(--radius)", padding: "12px 14px 12px 38px",
                fontSize: "0.9rem", fontFamily: "inherit", color: "var(--ink)",
                background: "#fafbff", outline: "none",
              }}
            />
          </div>
          <button type="submit" className="primary-button" style={{ padding: "12px 22px", whiteSpace: "nowrap" }}>
            Buscar
          </button>
        </form>
      </section>

      {loading && <LoadingBlock label="Localizando processo..." />}
      {error   && <ErrorBlock message={error} />}

      {data && !loading && (
        <>
          {!data.encontrado ? (
            <section className="panel" style={{ textAlign: "center", padding: "40px 24px", color: "var(--muted)" }}>
              Nenhum processo encontrado para <strong style={{ color: "var(--ink)" }}>"{q}"</strong>.
              Verifique o número e tente novamente.
            </section>
          ) : (
            <>
              <div style={{ fontSize: "0.82rem", color: "var(--muted)", paddingLeft: 2 }}>
                {data.total} processo{data.total !== 1 ? "s" : ""} encontrado{data.total !== 1 ? "s" : ""}
                {data.total > 20 && " — exibindo os 20 primeiros resultados"}
              </div>
              {data.resultados.map((proc) => (
                <ProcessCard key={proc.protocolo} proc={proc} />
              ))}
            </>
          )}
        </>
      )}

      {!q && !loading && (
        <section className="panel" style={{ textAlign: "center", padding: "40px 24px", color: "var(--muted)" }}>
          Digite o número do protocolo acima para iniciar a busca.
        </section>
      )}
    </div>
  );
}
