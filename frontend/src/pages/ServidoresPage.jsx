import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LineChartCard from "../charts/LineChartCard";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useFilters } from "../context/FiltersContext";


/* ── Configurações de status ───────────────────── */
const STATUS = {
  sobrecarga: { label: "Sobrecarga", bg: "rgba(191,53,53,0.1)",   color: "#bf3535", bar: "#bf3535" },
  elevada:    { label: "Elevada",    bg: "rgba(212,117,14,0.1)",   color: "#d4750e", bar: "#d4750e" },
  normal:     { label: "Normal",     bg: "rgba(39,49,104,0.07)",   color: "#273168", bar: "#273168" },
  baixa:      { label: "Baixa",      bg: "rgba(129,199,238,0.18)", color: "#2a7aad", bar: "#81c7ee" },
};

function StatusBadge({ status }) {
  const cfg = STATUS[status] || STATUS.normal;
  return (
    <span style={{
      padding: "3px 10px", borderRadius: 999, fontSize: "0.72rem", fontWeight: 700,
      background: cfg.bg, color: cfg.color,
    }}>
      {cfg.label}
    </span>
  );
}

function Delta({ value }) {
  if (value === null || value === undefined) return <span style={{ color: "var(--muted)" }}>—</span>;
  if (value === 0) return <span style={{ color: "var(--muted)" }}>—</span>;
  const up = value > 0;
  return (
    <span style={{ fontWeight: 700, color: up ? "#bf3535" : "#1a7a50", fontSize: "0.82rem" }}>
      {up ? "▲" : "▼"} {Math.abs(value)}
    </span>
  );
}

function fmtDate(val) {
  if (!val) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${val}T00:00:00Z`));
  } catch { return val; }
}

function shortName(name, maxLen = 18) {
  if (!name || name.length <= maxLen) return name;
  return name.slice(0, maxLen - 1) + "…";
}


/* ── Componente: Balanceamento ──────────────────── */
function BalanceSection({ filters }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    const params = {};
    if (filters.data_referencia) params.data_referencia = filters.data_referencia;
    if (filters.setor)           params.setor           = filters.setor;

    api.get("/analytics/workload-balance", { params })
      .then(({ data: res }) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "Falha ao carregar balanceamento."); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [filters.data_referencia, filters.setor, retryCount]);

  if (loading) return <LoadingBlock label="Calculando balanceamento de carteiras..." />;
  if (error)   return <ErrorBlock message={error} onRetry={() => setRetryCount((c) => c + 1)} />;
  if (!data || !data.servidores?.length) return (
    <section className="panel" style={{ textAlign: "center", padding: "32px", color: "var(--muted)" }}>
      Nenhum dado de balanceamento disponível para os filtros selecionados.
    </section>
  );

  const { stats, servidores, data_referencia, data_anterior } = data;

  const deltaTotal = stats.delta_total;
  const chartData = servidores.map((s) => ({
    ...s,
    label: shortName(s.atribuicao),
  }));

  return (
    <>
      {/* Alerta de sobrecarga */}
      {stats.em_sobrecarga > 0 && (
        <div className="alert error" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          ⚠️ {stats.em_sobrecarga} servidor{stats.em_sobrecarga > 1 ? "es" : ""} em situação de
          sobrecarga (carga &gt; 1,5× a média).
        </div>
      )}

      {/* Stats */}
      <section className="stats-grid">
        <StatCard label="Total distribuído" value={stats.total_processos}
          hint={deltaTotal !== null ? (deltaTotal >= 0 ? `+${deltaTotal} vs snapshot anterior` : `${deltaTotal} vs snapshot anterior`) : undefined} />
        <StatCard label="Servidores monitorados" value={stats.total_servidores} />
        <StatCard label="Média por servidor" value={`${stats.media_carga}`} hint={`Desvio: ±${stats.desvio_padrao}`} />
        <StatCard label="Em sobrecarga" value={stats.em_sobrecarga}
          hint={`Referência: ${fmtDate(data_referencia)}`} />
      </section>

      {/* Gráfico horizontal */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Carga atual por servidor</h3>
            <p>
              Linha pontilhada = média ({stats.media_carga} processos).
              {data_anterior && ` Comparado com snapshot de ${fmtDate(data_anterior)}.`}
            </p>
          </div>
          {/* Legenda de cores */}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {Object.entries(STATUS).map(([key, cfg]) => (
              <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 5,
                fontSize: "0.72rem", fontWeight: 700, color: cfg.color }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: cfg.bar, display: "inline-block" }} />
                {cfg.label}
              </span>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={Math.max(200, servidores.length * 36)}>
          <BarChart layout="vertical" data={chartData} margin={{ top: 4, right: 40, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(39,49,104,0.07)" />
            <XAxis type="number" tick={{ fontSize: 11, fill: "#5a6390" }} tickLine={false} />
            <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 11, fill: "#1a2050" }} tickLine={false} />
            <Tooltip
              formatter={(value, _, props) => [
                `${value} processos${props.payload?.delta !== null && props.payload?.delta !== undefined
                  ? ` (${props.payload.delta >= 0 ? "+" : ""}${props.payload.delta} vs anterior)` : ""}`,
                props.payload?.atribuicao || "Carga",
              ]}
              contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", fontSize: 12 }}
            />
            <ReferenceLine x={stats.media_carga} stroke="#f39320" strokeDasharray="5 3" strokeWidth={1.5} label={{
              value: `Média: ${stats.media_carga}`, position: "top", fontSize: 10, fill: "#d4750e",
            }} />
            <Bar dataKey="carga" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={STATUS[entry.status]?.bar || "#273168"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Tabela detalhada */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Detalhamento por servidor</h3>
            <p>% do total, variação desde o último snapshot e classificação de carga.</p>
          </div>
        </div>
        <div className="table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Servidor</th>
                <th style={{ textAlign: "right" }}>Carga atual</th>
                <th style={{ textAlign: "right" }}>% do total</th>
                <th style={{ textAlign: "center" }}>
                  Vs {data_anterior ? fmtDate(data_anterior) : "anterior"}
                </th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {servidores.map((s, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{s.atribuicao}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "var(--primary)" }}>{s.carga}</td>
                  <td style={{ textAlign: "right", color: "var(--muted)", fontSize: "0.82rem" }}>{s.pct_total}%</td>
                  <td style={{ textAlign: "center" }}><Delta value={s.delta} /></td>
                  <td><StatusBadge status={s.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}


/* ── Componente: Perfil do Servidor ─────────────── */
function ProfileSection({ filters, atribuicoes }) {
  const [selected, setSelected] = useState("");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selected) { setProfile(null); return; }
    let cancelled = false;
    setLoading(true);
    setError("");

    const params = { atribuicao: selected };
    if (filters.data_referencia) params.data_referencia = filters.data_referencia;

    api.get("/analytics/server-profile", { params })
      .then(({ data: res }) => { if (!cancelled) setProfile(res); })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "Falha ao carregar perfil."); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [selected, filters.data_referencia]);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>Perfil do servidor</h3>
          <p>Selecione um servidor para ver o histórico longitudinal de sua carteira.</p>
        </div>
      </div>

      <div style={{ maxWidth: 400, marginBottom: 20 }}>
        <label className="field">
          <span>Servidor</span>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">Selecione um servidor...</option>
            {atribuicoes.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
      </div>

      {loading && <LoadingBlock label="Carregando perfil do servidor..." />}
      {error   && <ErrorBlock message={error} />}

      {profile && !loading && (
        profile.encontrado ? (
          <>
            {/* Stats do perfil */}
            <div className="stats-grid" style={{ marginBottom: 20 }}>
              <StatCard label="Carga atual"           value={profile.carga_atual} />
              <StatCard label="Total recebidos"       value={profile.total_recebidos}
                hint="Processos que já passaram por este servidor" />
              <StatCard label="Finalizados / saídas"  value={profile.total_finalizados}
                hint="Processos que saíram da carteira deste servidor" />
              <StatCard label="Média de permanência"
                value={profile.media_permanencia_dias !== null ? `${profile.media_permanencia_dias}d` : "—"}
                hint="Tempo médio que um processo fica com este servidor" />
            </div>

            {/* Gráfico histórico */}
            {profile.carga_historica.length > 1 && (
              <LineChartCard
                title={`Evolução da carteira — ${profile.atribuicao}`}
                subtitle="Quantidade de processos atribuídos a este servidor em cada data de upload."
                data={profile.carga_historica}
                xKey="data"
                valueKey="carga"
              />
            )}

            {/* Info de resumo */}
            <div style={{ marginTop: 14, padding: "12px 16px", borderRadius: "var(--radius)",
              background: "var(--primary-light)", fontSize: "0.82rem", color: "var(--muted)" }}>
              <strong style={{ color: "var(--ink)" }}>Referência:</strong> {fmtDate(profile.data_referencia)} ·
              <strong style={{ color: "var(--ink)" }}> Em aberto:</strong> {profile.em_aberto} processos
              ainda na carteira deste servidor.
            </div>
          </>
        ) : (
          <div style={{ color: "var(--muted)", padding: "20px 0" }}>
            Nenhum dado encontrado para este servidor no período selecionado.
          </div>
        )
      )}

      {!selected && !loading && (
        <div style={{ color: "var(--muted)", padding: "20px 0", fontSize: "0.875rem" }}>
          Escolha um servidor no campo acima para visualizar o histórico completo de sua carteira.
        </div>
      )}
    </section>
  );
}


/* ── Página principal ───────────────────────────── */
export default function ServidoresPage() {
  const { filters, options } = useFilters();
  const [tab, setTab] = useState("balance");

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Gestão de carga</p>
          <h1>Servidores e carteiras</h1>
          <span>
            Balanceamento de carga entre servidores, comparativo com o snapshot anterior
            e histórico longitudinal individual por servidor.
          </span>
        </div>
      </section>

      {/* Abas */}
      <section className="panel">
        <div className="tab-strip">
          <button
            type="button"
            className={`tab-button ${tab === "balance" ? "active" : ""}`}
            onClick={() => setTab("balance")}
          >
            Balanceamento de carteiras
          </button>
          <button
            type="button"
            className={`tab-button ${tab === "profile" ? "active" : ""}`}
            onClick={() => setTab("profile")}
          >
            Perfil do servidor
          </button>
        </div>
      </section>

      {tab === "balance" && <BalanceSection filters={filters} />}
      {tab === "profile" && (
        <ProfileSection filters={filters} atribuicoes={options.atribuicoes || []} />
      )}
    </div>
  );
}
