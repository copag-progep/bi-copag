import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import { useAuth } from "../context/AuthContext";
import { useFilters } from "../context/FiltersContext";

const STATUS_CFG = {
  pendente:          { label: "Pendente",           color: "#8a5b00",   bg: "rgba(254,187,18,.14)" },
  em_acompanhamento: { label: "Em acompanhamento",  color: "#273168",   bg: "rgba(39,49,104,.1)"  },
  saiu_do_setor:     { label: "Saiu do setor",      color: "#1a7a50",   bg: "rgba(26,122,80,.1)"  },
  resolvido_manual:  { label: "Resolvido",           color: "#1a7a50",   bg: "rgba(26,122,80,.1)"  },
  arquivado:         { label: "Arquivado",           color: "var(--muted)", bg: "rgba(0,0,0,.06)" },
};

const NIVEL_CFG = {
  critico:  { color: "#bf3535", bg: "rgba(191,53,53,.1)"  },
  elevado:  { color: "#d4750e", bg: "rgba(212,117,14,.1)" },
  moderado: { color: "#8a5b00", bg: "rgba(138,91,0,.1)"   },
  normal:   { color: "#1a7a50", bg: "rgba(26,122,80,.08)" },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pendente;
  return (
    <span style={{
      padding: "2px 9px", borderRadius: 8, fontSize: "0.73rem", fontWeight: 700,
      color: cfg.color, background: cfg.bg, whiteSpace: "nowrap",
    }}>
      {cfg.label}
    </span>
  );
}

function NivelBadge({ nivel }) {
  if (!nivel) return <span style={{ color: "var(--muted)" }}>—</span>;
  const cfg = NIVEL_CFG[nivel] || {};
  return (
    <span style={{
      padding: "2px 9px", borderRadius: 8, fontSize: "0.73rem", fontWeight: 700,
      color: cfg.color, background: cfg.bg, whiteSpace: "nowrap",
    }}>
      {nivel.charAt(0).toUpperCase() + nivel.slice(1)}
    </span>
  );
}

function KpiPill({ label, value, color }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
      padding: "10px 18px", borderRadius: 10, background: "rgba(255,255,255,.1)",
      border: "1px solid rgba(255,255,255,.15)",
    }}>
      <strong style={{ fontSize: "1.4rem", fontWeight: 800, color: color || "#fff", lineHeight: 1 }}>
        {value}
      </strong>
      <small style={{ fontSize: "0.68rem", fontWeight: 700, color: "rgba(255,255,255,.7)", textTransform: "uppercase", letterSpacing: ".06em" }}>
        {label}
      </small>
    </div>
  );
}

// ── Formulário: copiar pendências para nova sessão ────────────────────────
function CopiarPendenciasForm({ sessaoId, onCreated, onCancel }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ titulo: "", data_inicio: today, data_fim: "", data_reuniao: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const { data } = await api.post(`/pauta/sessoes/${sessaoId}/copy-pending`, {
        titulo: form.titulo,
        data_inicio: form.data_inicio,
        data_fim: form.data_fim || null,
        data_reuniao: form.data_reuniao || null,
      });
      onCreated(data);
    } catch (ex) {
      setErr(ex.response?.data?.detail || "Falha ao copiar pendências.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <label className="field">
        <span>Título da nova sessão</span>
        <input type="text" required value={form.titulo}
          onChange={(e) => setForm((p) => ({ ...p, titulo: e.target.value }))}
          placeholder="ex: Pauta COPAG — Semana 10/06 a 14/06" />
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        <label className="field">
          <span>Início do período</span>
          <input type="date" required value={form.data_inicio}
            onChange={(e) => setForm((p) => ({ ...p, data_inicio: e.target.value }))} />
        </label>
        <label className="field">
          <span>Fim do período</span>
          <input type="date" value={form.data_fim}
            onChange={(e) => setForm((p) => ({ ...p, data_fim: e.target.value }))} />
        </label>
        <label className="field">
          <span>Data da reunião</span>
          <input type="date" value={form.data_reuniao}
            onChange={(e) => setForm((p) => ({ ...p, data_reuniao: e.target.value }))} />
        </label>
      </div>
      {err && <div style={{ color: "#bf3535", fontSize: "0.85rem", fontWeight: 600 }}>{err}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="primary-button" disabled={saving} style={{ fontSize: "0.85rem", padding: "8px 18px" }}>
          {saving ? "Copiando..." : "Criar nova sessão com pendências"}
        </button>
        <button type="button" className="ghost-button" onClick={onCancel} style={{ fontSize: "0.85rem" }}>Cancelar</button>
      </div>
    </form>
  );
}


// ── Formulário de nova sessão ─────────────────────────────────────────────
function NovaSessaoForm({ onCreated, onCancel }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    titulo: "",
    data_inicio: today,
    data_fim: "",
    data_reuniao: "",
    observacoes: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const { data } = await api.post("/pauta/sessoes", {
        titulo: form.titulo,
        data_inicio: form.data_inicio,
        data_fim: form.data_fim || null,
        data_reuniao: form.data_reuniao || null,
        observacoes: form.observacoes || null,
      });
      onCreated(data.id);
    } catch (e) {
      setErr(e.response?.data?.detail || "Falha ao criar sessão.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <label className="field">
        <span>Título da sessão</span>
        <input type="text" required value={form.titulo}
          onChange={(e) => setForm((p) => ({ ...p, titulo: e.target.value }))}
          placeholder="ex: Pauta COPAG — Semana 03/06 a 07/06" />
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        <label className="field">
          <span>Início do período</span>
          <input type="date" required value={form.data_inicio}
            onChange={(e) => setForm((p) => ({ ...p, data_inicio: e.target.value }))} />
        </label>
        <label className="field">
          <span>Fim do período</span>
          <input type="date" value={form.data_fim}
            onChange={(e) => setForm((p) => ({ ...p, data_fim: e.target.value }))} />
        </label>
        <label className="field">
          <span>Data da reunião</span>
          <input type="date" value={form.data_reuniao}
            onChange={(e) => setForm((p) => ({ ...p, data_reuniao: e.target.value }))} />
        </label>
      </div>
      <label className="field">
        <span>Observações gerais</span>
        <input type="text" value={form.observacoes}
          onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
          placeholder="Contexto ou foco da sessão (opcional)" />
      </label>
      {err && <div style={{ color: "#bf3535", fontSize: "0.85rem", fontWeight: 600 }}>{err}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="primary-button" disabled={saving} style={{ fontSize: "0.85rem", padding: "8px 18px" }}>
          {saving ? "Criando..." : "Criar sessão"}
        </button>
        <button type="button" className="ghost-button" onClick={onCancel} style={{ fontSize: "0.85rem" }}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ── Modal: adicionar processos do Score de Risco ──────────────────────────
function AdicionarProcessosModal({ sessaoId, users, onClose, onAdded }) {
  const { toQueryParams } = useFilters();
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroNivel, setFiltroNivel] = useState("todos");
  const [filtroSetor, setFiltroSetor] = useState("");
  const [filtroDias, setFiltroDias] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [assignTo, setAssignTo] = useState("");
  const [nota, setNota] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/analytics/risk-score", { params: toQueryParams() })
      .then((r) => setRiskData(r.data))
      .catch(() => setRiskData(null))
      .finally(() => setLoading(false));
  }, []);

  const processos = (riskData?.processos || []).filter((p) => {
    if (filtroNivel !== "todos" && p.nivel !== filtroNivel) return false;
    if (filtroSetor && p.setor !== filtroSetor) return false;
    if (filtroDias && p.dias_no_setor < Number(filtroDias)) return false;
    return p.nivel !== "normal";
  });

  const setores = [...new Set((riskData?.processos || []).map((p) => p.setor))].sort();

  function toggleSelect(key) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === processos.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(processos.map((p) => `${p.protocolo}|${p.setor}|${p.entrada_setor || ""}`)));
    }
  }

  async function handleAdicionar() {
    if (!selected.size) return;
    setSaving(true);
    setErr("");
    const itens = processos
      .filter((p) => selected.has(`${p.protocolo}|${p.setor}|${p.entrada_setor || ""}`))
      .map((p) => ({
        protocolo: p.protocolo,
        setor: p.setor,
        entrada_setor: p.entrada_setor || null,
        data_referencia: riskData?.data_referencia || null,
        ultima_presenca: riskData?.data_referencia || null,
        atribuicao: p.atribuicao || null,
        tipo: p.tipo || null,
        dias_no_setor: p.dias_no_setor,
        score_risco: p.score,
        nivel_risco: p.nivel,
      }));
    try {
      const { data } = await api.post(`/pauta/sessoes/${sessaoId}/itens/bulk`, {
        sessao_id: sessaoId,
        assigned_to: assignTo ? Number(assignTo) : null,
        nota_admin: nota || null,
        itens,
      });
      onAdded(data.added);
    } catch (e) {
      setErr(e.response?.data?.detail || "Falha ao adicionar processos.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
    }}>
      <div style={{
        background: "var(--panel)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)",
        boxShadow: "0 20px 60px rgba(0,0,0,.25)", width: "100%", maxWidth: 900,
        maxHeight: "90vh", display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3 style={{ margin: 0, color: "var(--ink)" }}>Adicionar do Score de Risco</h3>
            <p style={{ margin: "4px 0 0", fontSize: "0.82rem", color: "var(--muted)" }}>
              Selecione os processos para incluir na pauta. Processos normais são omitidos.
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={onClose} style={{ fontSize: "1.2rem" }}>✕</button>
        </div>

        <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--border)", display: "flex", gap: 10, flexWrap: "wrap" }}>
          {["todos", "critico", "elevado", "moderado"].map((n) => (
            <button key={n} type="button"
              className={`risk-filter-pill ${filtroNivel === n ? "active" : ""}`}
              onClick={() => setFiltroNivel(n)}
              style={{ textTransform: "capitalize" }}>
              {n === "todos" ? "Todos os níveis" : n.charAt(0).toUpperCase() + n.slice(1)}
            </button>
          ))}
          <select value={filtroSetor} onChange={(e) => setFiltroSetor(e.target.value)}
            style={{ border: "1.5px solid var(--border-strong)", borderRadius: 999, padding: "6px 14px", fontSize: "0.8rem", fontFamily: "inherit", color: "var(--ink)", background: "var(--bg)" }}>
            <option value="">Todos os setores</option>
            {setores.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input type="number" placeholder="Dias mínimos" value={filtroDias}
            onChange={(e) => setFiltroDias(e.target.value)}
            style={{ width: 130, border: "1.5px solid var(--border-strong)", borderRadius: 999, padding: "6px 14px", fontSize: "0.8rem", fontFamily: "inherit", color: "var(--ink)", background: "var(--bg)" }} />
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "0 24px" }}>
          {loading ? (
            <LoadingBlock label="Carregando Score de Risco..." />
          ) : (
            <table className="data-table" style={{ fontSize: "0.8rem" }}>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" onChange={toggleAll}
                      checked={selected.size > 0 && selected.size === processos.length} />
                  </th>
                  <th>Protocolo</th>
                  <th>Setor</th>
                  <th>Tipo</th>
                  <th>Dias</th>
                  <th>Risco</th>
                </tr>
              </thead>
              <tbody>
                {processos.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--muted)", padding: 24 }}>
                    Nenhum processo encontrado para estes filtros.
                  </td></tr>
                ) : processos.map((p) => {
                  const key = `${p.protocolo}|${p.setor}|${p.entrada_setor || ""}`;
                  return (
                    <tr key={key} style={{ cursor: "pointer", background: selected.has(key) ? "var(--primary-light)" : "transparent" }}
                      onClick={() => toggleSelect(key)}>
                      <td><input type="checkbox" checked={selected.has(key)} onChange={() => toggleSelect(key)} onClick={(e) => e.stopPropagation()} /></td>
                      <td style={{ fontWeight: 600, fontSize: "0.78rem" }}>{p.protocolo}</td>
                      <td>{p.setor}</td>
                      <td style={{ color: "var(--muted)" }}>{p.tipo || "—"}</td>
                      <td><strong>{p.dias_no_setor}</strong></td>
                      <td><NivelBadge nivel={p.nivel} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div style={{ padding: "16px 24px", borderTop: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label className="field" style={{ flex: 1, minWidth: 180, margin: 0 }}>
            <span>Atribuir a</span>
            <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)}
              style={{ width: "100%" }}>
              <option value="">Sem atribuição</option>
              {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </label>
          <label className="field" style={{ flex: 2, minWidth: 200, margin: 0 }}>
            <span>Nota para o responsável</span>
            <input type="text" value={nota} onChange={(e) => setNota(e.target.value)}
              placeholder="Orientação ou contexto (opcional)" />
          </label>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <button type="button" className="primary-button" disabled={!selected.size || saving}
              onClick={handleAdicionar} style={{ fontSize: "0.85rem", padding: "10px 18px" }}>
              {saving ? "Adicionando..." : `Adicionar ${selected.size > 0 ? `(${selected.size})` : ""}`}
            </button>
            <button type="button" className="ghost-button" onClick={onClose} style={{ fontSize: "0.85rem" }}>
              Cancelar
            </button>
          </div>
          {err && <div style={{ width: "100%", color: "#bf3535", fontSize: "0.82rem", fontWeight: 600 }}>{err}</div>}
        </div>
      </div>
    </div>
  );
}

// ── Linha de item com edição inline ──────────────────────────────────────
function PautaItemRow({ item, isAdmin, onUpdated, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [nota, setNota] = useState(item.nota_responsavel || "");
  const [saving, setSaving] = useState(false);

  async function handleStatusChange(newStatus) {
    setSaving(true);
    try {
      await api.patch(`/pauta/itens/${item.id}`, { status: newStatus });
      onUpdated();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  async function saveNota() {
    setSaving(true);
    try {
      await api.patch(`/pauta/itens/${item.id}`, { nota_responsavel: nota });
      setEditing(false);
      onUpdated();
    } finally {
      setSaving(false);
    }
  }

  const isActive = ["pendente", "em_acompanhamento"].includes(item.status);

  return (
    <tr style={{ background: !isActive ? "rgba(0,0,0,.02)" : undefined, opacity: item.status === "arquivado" ? .5 : 1 }}>
      <td style={{ fontWeight: 600, fontSize: "0.78rem", color: "var(--primary)" }}>{item.protocolo}</td>
      <td>
        <span style={{ padding: "1px 7px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 700, background: "var(--primary-light)", color: "var(--primary)" }}>
          {item.setor}
        </span>
      </td>
      <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>{item.tipo || "—"}</td>
      <td><strong>{item.dias_no_setor ?? "—"}</strong></td>
      <td><NivelBadge nivel={item.nivel_risco} /></td>
      <td style={{ fontSize: "0.78rem" }}>{item.assigned_to_nome || <span style={{ color: "var(--muted)", fontStyle: "italic" }}>Sem atribuição</span>}</td>
      <td><StatusBadge status={item.status} /></td>
      <td style={{ fontSize: "0.78rem", color: "var(--muted)", maxWidth: 200 }}>
        {item.nota_admin || "—"}
      </td>
      <td>
        {editing ? (
          <div style={{ display: "flex", gap: 4 }}>
            <input type="text" value={nota} onChange={(e) => setNota(e.target.value)}
              style={{ width: 160, padding: "3px 8px", borderRadius: 6, border: "1.5px solid var(--primary)", fontSize: "0.78rem" }} />
            <button type="button" className="table-button" disabled={saving} onClick={saveNota}
              style={{ fontSize: "0.72rem", padding: "3px 8px" }}>✓</button>
            <button type="button" className="ghost-button" onClick={() => setEditing(false)}
              style={{ fontSize: "0.72rem" }}>✕</button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ fontSize: "0.78rem", color: item.nota_responsavel ? "var(--ink)" : "var(--muted)", fontStyle: item.nota_responsavel ? "normal" : "italic" }}>
              {item.nota_responsavel || "—"}
            </span>
            <button type="button" className="ghost-button" onClick={() => setEditing(true)}
              style={{ fontSize: "0.7rem", padding: "1px 6px" }}>✎</button>
          </div>
        )}
      </td>
      <td>
        <div style={{ display: "flex", gap: 4, flexWrap: "nowrap" }}>
          {item.status === "pendente" && (
            <button type="button" className="table-button" disabled={saving}
              onClick={() => handleStatusChange("em_acompanhamento")}
              style={{ fontSize: "0.7rem", padding: "3px 8px", whiteSpace: "nowrap" }}>
              Confirmar ciência
            </button>
          )}
          {isActive && (
            <button type="button" className="table-button" disabled={saving}
              onClick={() => handleStatusChange("resolvido_manual")}
              style={{ fontSize: "0.7rem", padding: "3px 8px" }}>
              ✓ Resolvido
            </button>
          )}
          {isAdmin && (
            <button type="button" className="ghost-button" disabled={saving}
              onClick={() => { if (window.confirm("Remover este processo da pauta?")) onDelete(item.id); }}
              style={{ fontSize: "0.7rem", color: "#bf3535" }}>✕</button>
          )}
        </div>
      </td>
    </tr>
  );
}


// ── Página principal ──────────────────────────────────────────────────────
export default function PautaPage() {
  const { user } = useAuth();
  const [sessoes, setSessoes] = useState([]);
  const [sessaoAtual, setSessaoAtual] = useState(null);
  const [sessaoData, setSessaoData] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingSessao, setLoadingSessao] = useState(false);
  const [error, setError] = useState("");
  const [showNovaSessao, setShowNovaSessao] = useState(false);
  const [showAdicionarModal, setShowAdicionarModal] = useState(false);
  const [showCopiarForm, setShowCopiarForm] = useState(false);
  const [msg, setMsg] = useState("");

  async function loadSessoes() {
    try {
      const { data } = await api.get("/pauta/sessoes", { params: { ativa: true } });
      setSessoes(data);
      if (!sessaoAtual && data.length > 0) setSessaoAtual(data[0].id);
    } catch {
      setError("Falha ao carregar pautas.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSessaoData(id) {
    if (!id) return;
    setLoadingSessao(true);
    try {
      const { data } = await api.get(`/pauta/sessoes/${id}`);
      setSessaoData(data);
    } catch {
      // ignore
    } finally {
      setLoadingSessao(false);
    }
  }

  useEffect(() => {
    loadSessoes();
    if (user?.is_admin) {
      api.get("/admin/users").then((r) => setUsers(r.data)).catch(() => {});
    }
  }, []);

  useEffect(() => {
    if (sessaoAtual) loadSessaoData(sessaoAtual);
  }, [sessaoAtual]);

  async function handleDeleteItem(itemId) {
    try {
      await api.delete(`/pauta/itens/${itemId}`);
      loadSessaoData(sessaoAtual);
    } catch {
      setMsg("✗ Falha ao remover item.");
    }
  }

  if (loading) return <LoadingBlock label="Carregando pauta..." />;
  if (error) return <ErrorBlock message={error} onRetry={loadSessoes} />;

  const contagens = sessaoData?.contagens || {};
  const itens = sessaoData?.itens || [];
  const totalAtivos = (contagens.pendente || 0) + (contagens.em_acompanhamento || 0);
  const totalResolvidos = (contagens.saiu_do_setor || 0) + (contagens.resolvido_manual || 0);

  return (
    <div className="page-grid">
      {/* Hero */}
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Gestão executiva</p>
          <h1>Pauta Prioritária</h1>
          <p>Processos críticos selecionados para acompanhamento semanal.</p>
        </div>
        {sessaoData && (
          <div style={{ display: "flex", gap: 10, flexShrink: 0, flexWrap: "wrap" }}>
            <KpiPill label="Pendentes" value={contagens.pendente || 0} />
            <KpiPill label="Em acomp." value={contagens.em_acompanhamento || 0} color="var(--yellow)" />
            <KpiPill label="Resolvidos" value={totalResolvidos} color="#4ade80" />
          </div>
        )}
      </section>

      {/* Seletor de sessão + ações */}
      <section className="panel" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 200 }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--muted)", whiteSpace: "nowrap" }}>Sessão:</span>
            <select value={sessaoAtual || ""} onChange={(e) => setSessaoAtual(Number(e.target.value))}
              style={{ flex: 1, border: "1.5px solid var(--border-strong)", borderRadius: 8, padding: "7px 12px", fontSize: "0.85rem", fontFamily: "inherit", color: "var(--ink)", background: "var(--bg)" }}>
              {sessoes.map((s) => (
                <option key={s.id} value={s.id}>{s.titulo} · {s.data_inicio}</option>
              ))}
              {sessoes.length === 0 && <option value="">Nenhuma sessão ativa</option>}
            </select>
          </label>
          {user?.is_admin && (
            <>
              <button type="button" className="primary-button" onClick={() => setShowNovaSessao(true)}
                style={{ fontSize: "0.82rem", padding: "8px 16px", whiteSpace: "nowrap" }}>
                + Nova sessão
              </button>
              {sessaoAtual && (
                <>
                  <button type="button" className="table-button" onClick={() => setShowAdicionarModal(true)}
                    style={{ fontSize: "0.82rem", padding: "8px 16px", whiteSpace: "nowrap" }}>
                    + Adicionar processos
                  </button>
                  {(sessaoData?.contagens?.pendente > 0 || sessaoData?.contagens?.em_acompanhamento > 0) && (
                    <button type="button" className="ghost-button" onClick={() => setShowCopiarForm(true)}
                      style={{ fontSize: "0.82rem", padding: "8px 16px", whiteSpace: "nowrap" }}
                      title="Copia itens pendentes desta sessão para uma nova sessão">
                      ↗ Copiar pendências
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {msg && (
          <div style={{
            marginTop: 10, padding: "8px 14px", borderRadius: 8,
            background: msg.startsWith("✓") ? "rgba(26,122,80,.1)" : "rgba(191,53,53,.1)",
            color: msg.startsWith("✓") ? "#1a7a50" : "#bf3535",
            fontSize: "0.85rem", fontWeight: 600,
          }}>
            {msg}
          </div>
        )}
      </section>

      {/* Formulário: copiar pendências para nova sessão */}
      {showCopiarForm && sessaoAtual && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>Copiar pendências para nova sessão</h3>
              <p>
                Copia processos com status <strong>Pendente</strong> e <strong>Em acompanhamento</strong> desta sessão para uma nova.
                Os itens originais permanecem intactos.
              </p>
            </div>
          </div>
          <CopiarPendenciasForm
            sessaoId={sessaoAtual}
            onCreated={(nova) => {
              setShowCopiarForm(false);
              setMsg(`✓ ${nova.itens_copiados} item(s) copiado(s) para "${nova.titulo}".`);
              loadSessoes().then(() => setSessaoAtual(nova.nova_sessao_id));
            }}
            onCancel={() => setShowCopiarForm(false)}
          />
        </section>
      )}

      {/* Formulário nova sessão */}
      {showNovaSessao && (
        <section className="panel">
          <div className="panel-header"><div><h3>Nova sessão de pauta</h3></div></div>
          <NovaSessaoForm
            onCreated={(id) => { setShowNovaSessao(false); loadSessoes().then(() => setSessaoAtual(id)); }}
            onCancel={() => setShowNovaSessao(false)}
          />
        </section>
      )}

      {/* Tabela de itens */}
      {sessaoAtual && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>
                {sessaoData?.titulo || "Carregando..."}
                {sessaoData?.data_reuniao && (
                  <span style={{ marginLeft: 10, fontSize: "0.78rem", fontWeight: 600, color: "var(--muted)" }}>
                    Reunião: {new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${sessaoData.data_reuniao}T00:00:00Z`))}
                  </span>
                )}
              </h3>
              <p>
                {itens.length} processo{itens.length !== 1 ? "s" : ""} · {totalAtivos} ativo{totalAtivos !== 1 ? "s" : ""} · {totalResolvidos} resolvido{totalResolvidos !== 1 ? "s" : ""}
                {sessaoData?.observacoes && <span> · {sessaoData.observacoes}</span>}
              </p>
            </div>
          </div>

          {loadingSessao ? (
            <LoadingBlock label="Carregando itens..." />
          ) : itens.length === 0 ? (
            <div className="empty-state">
              {user?.is_admin
                ? 'Nenhum processo nesta pauta. Clique em "+ Adicionar processos" para começar.'
                : "Nenhum processo atribuído a você nesta sessão."}
            </div>
          ) : (
            <div className="table-shell" style={{ overflowX: "auto" }}>
              <table className="data-table" style={{ fontSize: "0.82rem", minWidth: 900 }}>
                <thead>
                  <tr>
                    <th>Protocolo</th>
                    <th>Setor</th>
                    <th>Tipo</th>
                    <th>Dias</th>
                    <th>Risco</th>
                    <th>Responsável</th>
                    <th>Status</th>
                    <th>Nota gestão</th>
                    <th>Nota responsável</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {itens.map((item) => (
                    <PautaItemRow
                      key={item.id}
                      item={item}
                      isAdmin={user?.is_admin}
                      onUpdated={() => loadSessaoData(sessaoAtual)}
                      onDelete={handleDeleteItem}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {!sessaoAtual && !showNovaSessao && (
        <div className="empty-state panel" style={{ padding: 40, textAlign: "center" }}>
          {user?.is_admin
            ? 'Nenhuma sessão ativa. Clique em "+ Nova sessão" para criar a primeira pauta.'
            : "Nenhuma pauta ativa no momento. Aguarde o administrador criar uma sessão."}
        </div>
      )}

      {/* Modal de adicionar processos */}
      {showAdicionarModal && sessaoAtual && (
        <AdicionarProcessosModal
          sessaoId={sessaoAtual}
          users={users.filter((u) => !u.is_admin)}
          onClose={() => setShowAdicionarModal(false)}
          onAdded={(count) => {
            setShowAdicionarModal(false);
            setMsg(`✓ ${count} processo${count !== 1 ? "s" : ""} adicionado${count !== 1 ? "s" : ""} à pauta.`);
            loadSessaoData(sessaoAtual);
          }}
        />
      )}
    </div>
  );
}
