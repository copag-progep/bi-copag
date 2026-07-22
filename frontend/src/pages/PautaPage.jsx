import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import api from "../api/client";
import ErrorBlock from "../components/ErrorBlock";
import LoadingBlock from "../components/LoadingBlock";
import { useAuth } from "../context/AuthContext";
import { useFilters } from "../context/FiltersContext";
import { generatePautaPdf } from "../utils/generatePautaPdf";

const STATUS_CFG = {
  pendente:          { label: "Pendente",                  color: "#8a5b00",      bg: "rgba(254,187,18,.14)" },
  em_acompanhamento: { label: "Em acompanhamento",         color: "#273168",      bg: "rgba(39,49,104,.1)"  },
  saiu_do_setor:     { label: "✓ Resolvido automaticamente", color: "#1a7a50",   bg: "rgba(26,122,80,.1)"  },
  resolvido_manual:  { label: "✓ Resolvido manualmente",  color: "#1a7a50",      bg: "rgba(26,122,80,.1)"  },
  arquivado:         { label: "Arquivado",                 color: "var(--muted)", bg: "rgba(0,0,0,.06)"     },
};

const NIVEL_CFG = {
  critico:  { color: "#bf3535", bg: "rgba(191,53,53,.1)"  },
  elevado:  { color: "#d4750e", bg: "rgba(212,117,14,.1)" },
  moderado: { color: "#8a5b00", bg: "rgba(138,91,0,.1)"   },
  normal:   { color: "#1a7a50", bg: "rgba(26,122,80,.08)" },
};

function isItemResolvido(status) {
  return status === "saiu_do_setor" || status === "resolvido_manual";
}

function StatusBadge({ status, dataStatus }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.pendente;
  const dateStr = dataStatus
    ? new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${dataStatus}T00:00:00Z`))
    : null;
  const isResolved = isItemResolvido(status);
  return (
    <span
      className="pauta-status-badge"
      style={{ color: cfg.color, background: cfg.bg }}
      title={isResolved && dateStr ? `${cfg.label} em ${dateStr}` : undefined}
    >
      {cfg.label}
      {isResolved && dateStr && (
        <span style={{ marginLeft: 5, fontWeight: 500, opacity: 0.8 }}>· {dateStr}</span>
      )}
    </span>
  );
}

const PAUTA_SORT_DEFAULT = {
  protocolo: "asc",
  setor: "asc",
  atribuicao: "asc",
  tipo: "asc",
  dias_no_setor: "desc",
  score_risco: "desc",
  responsavel: "asc",
  status: "asc",
  prazo: "desc",
  dias_prazo: "desc",
  nota_admin: "asc",
};

const PAUTA_TEXT_SORTS = new Set(["protocolo", "setor", "atribuicao", "tipo", "responsavel", "status", "nota_admin"]);

function pautaSortValue(item, key) {
  if (key === "atribuicao") return item.atribuicao_display ?? item.atribuicao;
  if (key === "responsavel") return item.assigned_to_nome;
  if (key === "status") return STATUS_CFG[item.status]?.label?.replace("✓ ", "") || item.status;
  if (key === "prazo") return item.prazo ? Date.parse(`${item.prazo}T00:00:00Z`) : null;
  if (key === "dias_prazo") return isItemResolvido(item.status) ? null : diffDias(item.prazo);
  if (key === "dias_no_setor") return item.dias_no_setor_atual ?? item.dias_no_setor;
  return item[key];
}

function sortPautaItems(items, sort) {
  const collator = new Intl.Collator("pt-BR", { sensitivity: "base", numeric: true });
  return items.map((item, index) => ({ item, index })).sort((aEntry, bEntry) => {
    const a = pautaSortValue(aEntry.item, sort.key);
    const b = pautaSortValue(bEntry.item, sort.key);
    const aEmpty = a === null || a === undefined || a === "";
    const bEmpty = b === null || b === undefined || b === "";
    if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
    if (aEmpty && bEmpty) return aEntry.index - bEntry.index;

    const comparison = PAUTA_TEXT_SORTS.has(sort.key)
      ? collator.compare(String(a), String(b))
      : Number(a) - Number(b);
    if (comparison !== 0) return sort.dir === "asc" ? comparison : -comparison;
    if (sort.key === "score_risco") {
      const byDays = Number(bEntry.item.dias_no_setor ?? -1) - Number(aEntry.item.dias_no_setor ?? -1);
      if (byDays !== 0) return byDays;
    }
    return collator.compare(aEntry.item.protocolo || "", bEntry.item.protocolo || "") || aEntry.index - bEntry.index;
  }).map(({ item }) => item);
}

function SortablePautaHeader({ column, children, sort, onSort, className = "" }) {
  const active = sort.key === column;
  const ariaSort = active ? (sort.dir === "asc" ? "ascending" : "descending") : "none";
  return (
    <th className={className} aria-sort={ariaSort}>
      <button type="button" className={`pauta-sort-button${active ? " active" : ""}`} onClick={() => onSort(column)}>
        <span>{children}</span>
        <span aria-hidden="true" className="pauta-sort-indicator">{active ? (sort.dir === "asc" ? "↑" : "↓") : "↕"}</span>
      </button>
    </th>
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

const SITUACAO_CFG = {
  a_iniciar:    { label: "A iniciar",    color: "var(--primary)", bg: "rgba(39,49,104,.1)"  },
  em_andamento: { label: "Em andamento", color: "#1a7a50",        bg: "rgba(26,122,80,.12)" },
  encerrada:    { label: "Encerrada",    color: "var(--muted)",   bg: "rgba(0,0,0,.06)"     },
};

function SituacaoBadge({ situacao, label }) {
  const cfg = SITUACAO_CFG[situacao] || SITUACAO_CFG.em_andamento;
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 999, fontSize: "0.72rem", fontWeight: 800,
      textTransform: "uppercase", letterSpacing: ".04em",
      color: cfg.color, background: cfg.bg, whiteSpace: "nowrap",
    }}>
      {label || cfg.label}
    </span>
  );
}

// ── Datas em America/Fortaleza (evita virada de dia por UTC) ──────────────
function hojeFortaleza() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Fortaleza" }).format(new Date());
}

function diffDias(dateStr) {
  if (!dateStr) return null;
  const MS_DIA = 86400000;
  return Math.round((Date.parse(`${dateStr}T00:00:00Z`) - Date.parse(`${hojeFortaleza()}T00:00:00Z`)) / MS_DIA);
}

function fmtData(dateStr) {
  if (!dateStr) return "—";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${dateStr}T00:00:00Z`));
}

function diasPrazoLabel(prazo, status) {
  if (isItemResolvido(status)) {
    return (
      <span
        style={{ color: "#1a7a50", fontWeight: 800, fontSize: "0.95rem", lineHeight: 1 }}
        title="Processo resolvido"
        aria-label="Processo resolvido"
      >
        ✓
      </span>
    );
  }
  if (!prazo) return <span style={{ color: "var(--muted)" }}>—</span>;
  const d = diffDias(prazo);
  const sinal = d < 0 ? "-" : "+";
  const num = String(Math.abs(d)).padStart(3, "0");
  return (
    <strong style={{ color: d < 0 ? "#bf3535" : "#1a7a50" }}>
      {sinal}{num}
    </strong>
  );
}

const MARCO_TONES = {
  ok:     { color: "var(--primary)", bg: "rgba(39,49,104,.07)" },
  warn:   { color: "#8a5b00",        bg: "rgba(254,187,18,.16)" },
  danger: { color: "#bf3535",        bg: "rgba(191,53,53,.1)"  },
  muted:  { color: "var(--muted)",   bg: "rgba(0,0,0,.04)"     },
  done:   { color: "#1a7a50",        bg: "rgba(26,122,80,.1)"  },
};

function inicioInfo(dataInicio) {
  const d = diffDias(dataInicio);
  if (d === null) return { label: "—", tone: "muted" };
  if (d > 0) return { label: d === 1 ? "Inicia amanhã" : `Inicia em ${d} dias`, tone: "muted" };
  if (d === 0) return { label: "Inicia hoje", tone: "ok" };
  return { label: d === -1 ? "Iniciada há 1 dia" : `Iniciada há ${-d} dias`, tone: "ok" };
}

function reuniaoInfo(dataReuniao) {
  const d = diffDias(dataReuniao);
  if (d === null) return { label: "Sem data definida", tone: "muted" };
  if (d > 0) return { label: d === 1 ? "Amanhã" : `Em ${d} dias`, tone: d <= 2 ? "warn" : "ok" };
  if (d === 0) return { label: "Hoje", tone: "warn" };
  return { label: d === -1 ? "Realizada há 1 dia" : `Realizada há ${-d} dias`, tone: "done" };
}

function prazoInfo(dataFim, totalAtivos) {
  const d = diffDias(dataFim);
  if (d === null) return { label: "Sem prazo definido", tone: "muted" };
  if (d > 0) return { label: d === 1 ? "Falta 1 dia" : `Faltam ${d} dias`, tone: d <= 3 ? "warn" : "ok" };
  if (d === 0) return { label: "Prazo termina hoje", tone: "warn" };
  if (totalAtivos > 0) return { label: d === -1 ? "Vencido há 1 dia" : `Vencido há ${-d} dias`, tone: "danger" };
  return { label: "Concluída no período", tone: "done" };
}

// ── Ícones (paths Lucide, inline — sem dependência nova) ─────────────────
function LucideIcon({ paths, size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}
const ICO = {
  plus:     ["M5 12h14", "M12 5v14"],
  fileDown: ["M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z", "M14 2v5h5", "M12 18v-6", "m9 15 3 3 3-3"],
  copy:     ["M8 8h12v12H8z", "M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"],
  more:     ["M11 12h2", "M4 12h2", "M18 12h2"],
  pencil:   ["M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"],
  archive:  ["M2 3h20v5H2z", "M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8", "M10 12h4"],
};

// ── Cronograma da sessão (visível para todos) ─────────────────────────────
function CronogramaSessao({ sessao, totalAtivos, isAdmin, onEditar }) {
  const marcos = [
    { titulo: "Início",         data: sessao.data_inicio,  info: inicioInfo(sessao.data_inicio) },
    { titulo: "Reunião",        data: sessao.data_reuniao, info: reuniaoInfo(sessao.data_reuniao) },
    { titulo: "Prazo da pauta", data: sessao.data_fim,     info: prazoInfo(sessao.data_fim, totalAtivos) },
  ];

  // Progresso temporal do período (só quando início e prazo existem)
  let pctTempo = null;
  const dIni = diffDias(sessao.data_inicio);
  const dFim = diffDias(sessao.data_fim);
  if (dIni !== null && dFim !== null && dFim > dIni) {
    pctTempo = Math.min(100, Math.max(0, Math.round((-dIni / (dFim - dIni)) * 100)));
  }

  return (
    <div className="pauta-cronograma">
      <div className="pauta-cronograma-marcos">
        {marcos.map((m) => {
          const tone = MARCO_TONES[m.info.tone];
          return (
            <div key={m.titulo} className="pauta-marco">
              <span className="pauta-marco-titulo">{m.titulo}</span>
              <strong className="pauta-marco-data">{fmtData(m.data)}</strong>
              <span className="pauta-marco-sub" style={{ color: tone.color, background: tone.bg }}>
                {m.info.label}
              </span>
            </div>
          );
        })}
        {isAdmin && (
          <button type="button" className="ghost-button pauta-marco-edit" onClick={onEditar}
            title="Editar título, datas e observações da sessão" aria-label="Editar sessão">
            <LucideIcon paths={ICO.pencil} size={14} />
          </button>
        )}
      </div>
      {pctTempo !== null && (
        <div className="pauta-tempo-track" title={`${pctTempo}% do período decorrido`}>
          <div className="pauta-tempo-fill" style={{ width: `${pctTempo}%` }} />
          <span className="pauta-tempo-label">{pctTempo}%</span>
        </div>
      )}
    </div>
  );
}

// ── Editor inline da sessão (admin) ───────────────────────────────────────
function SessaoEditForm({ sessao, onSaved, onCancel }) {
  const [form, setForm] = useState({
    titulo: sessao.titulo || "",
    data_inicio: sessao.data_inicio || "",
    data_reuniao: sessao.data_reuniao || "",
    data_fim: sessao.data_fim || "",
    observacoes: sessao.observacoes || "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Aviso (não bloqueio): reunião fora do período pode ser cobrança legítima
  const reuniaoForaDoPeriodo =
    form.data_reuniao && form.data_inicio &&
    (form.data_reuniao < form.data_inicio || (form.data_fim && form.data_reuniao > form.data_fim));

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.data_inicio) { setErr("Data de início é obrigatória."); return; }
    if (form.data_fim && form.data_inicio > form.data_fim) {
      setErr("O prazo da pauta não pode ser anterior à data de início.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      // Envia null explicitamente para limpar datas opcionais (backend usa exclude_unset)
      await api.patch(`/pauta/sessoes/${sessao.id}`, {
        titulo: form.titulo,
        data_inicio: form.data_inicio,
        data_reuniao: form.data_reuniao || null,
        data_fim: form.data_fim || null,
        observacoes: form.observacoes || null,
      });
      onSaved();
    } catch (ex) {
      setErr(ex.response?.data?.detail || "Falha ao salvar a sessão.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="pauta-edit-form">
      <label className="field">
        <span>Título da sessão</span>
        <input type="text" required minLength={3} value={form.titulo}
          onChange={(e) => setForm((p) => ({ ...p, titulo: e.target.value }))} />
      </label>
      <div className="pauta-edit-datas">
        <label className="field">
          <span>Início</span>
          <input type="date" required value={form.data_inicio}
            onChange={(e) => setForm((p) => ({ ...p, data_inicio: e.target.value }))} />
        </label>
        <label className="field">
          <span>Reunião</span>
          <input type="date" value={form.data_reuniao}
            onChange={(e) => setForm((p) => ({ ...p, data_reuniao: e.target.value }))} />
        </label>
        <label className="field">
          <span>Prazo da pauta</span>
          <input type="date" value={form.data_fim}
            onChange={(e) => setForm((p) => ({ ...p, data_fim: e.target.value }))} />
        </label>
      </div>
      <label className="field">
        <span>Observações</span>
        <input type="text" value={form.observacoes}
          onChange={(e) => setForm((p) => ({ ...p, observacoes: e.target.value }))}
          placeholder="Contexto ou foco da sessão (opcional)" />
      </label>
      {reuniaoForaDoPeriodo && (
        <div className="pauta-edit-aviso">
          ⚠ A data da reunião está fora do período da pauta — permitido, mas confira se é intencional.
        </div>
      )}
      {err && <div style={{ color: "#bf3535", fontSize: "0.85rem", fontWeight: 600 }}>{err}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="primary-button" disabled={saving}
          style={{ fontSize: "0.85rem", padding: "8px 18px" }}>
          {saving ? "Salvando..." : "Salvar alterações"}
        </button>
        <button type="button" className="ghost-button" onClick={onCancel} style={{ fontSize: "0.85rem" }}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ── Progresso de resolução (segmentado por status) ───────────────────────
function ProgressoResolucao({ contagens }) {
  const resolvidos = (contagens.saiu_do_setor || 0) + (contagens.resolvido_manual || 0);
  const acomp = contagens.em_acompanhamento || 0;
  const pendentes = contagens.pendente || 0;
  const total = resolvidos + acomp + pendentes; // arquivados fora do denominador
  if (total === 0) return null;

  const pct = (n) => `${(n / total) * 100}%`;
  return (
    <div className="pauta-progresso">
      <div className="pauta-progresso-track">
        {resolvidos > 0 && <div className="pauta-progresso-seg seg-resolvido" style={{ width: pct(resolvidos) }} />}
        {acomp > 0 && <div className="pauta-progresso-seg seg-acomp" style={{ width: pct(acomp) }} />}
        {pendentes > 0 && <div className="pauta-progresso-seg seg-pendente" style={{ width: pct(pendentes) }} />}
      </div>
      <div className="pauta-progresso-legenda">
        <strong>{resolvidos} de {total} processos resolvidos</strong>
        <span>
          <i className="dot dot-resolvido" /> {resolvidos} resolvidos ·{" "}
          <i className="dot dot-acomp" /> {acomp} em acompanhamento ·{" "}
          <i className="dot dot-pendente" /> {pendentes} pendentes
        </span>
      </div>
    </div>
  );
}

// ── Menu administrativo (⋯) ───────────────────────────────────────────────
function AdminMenu({ onEditar, onEncerrar, onCopiar, sessaoOperavel, temPendencias }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button type="button" className="ghost-button" onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu" aria-expanded={open} aria-label="Mais ações da sessão"
        style={{ padding: "8px 10px", display: "inline-flex" }}>
        <LucideIcon paths={ICO.more} size={16} />
      </button>
      {open && (
        <div className="pauta-admin-menu" role="menu">
          {/* Editar sempre disponível: admin pode corrigir prazo de sessão
              encerrada por engano; o backend recalcula a situação ao salvar */}
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onEditar(); }}>
            <LucideIcon paths={ICO.pencil} size={14} /> Editar sessão
          </button>
          {/* Copiar pendências: útil justamente ao fim do ciclo — liberado
              sempre que houver pendências, inclusive em sessão encerrada.
              Se a origem já está encerrada, o backend só copia (não re-encerra) */}
          {temPendencias && (
            <button type="button" role="menuitem"
              onClick={() => { setOpen(false); onCopiar(); }}
              title={sessaoOperavel
                ? "Encerra esta sessão e copia os pendentes para uma nova"
                : "Copia os pendentes desta sessão encerrada para uma nova"}>
              <LucideIcon paths={ICO.copy} size={14} />
              {sessaoOperavel ? " Encerrar e copiar pendências" : " Copiar pendências"}
            </button>
          )}
          {/* Encerrar: só faz sentido em sessão operável */}
          {sessaoOperavel && (
            <button type="button" role="menuitem" className="danger"
              onClick={() => { setOpen(false); onEncerrar(); }}>
              <LucideIcon paths={ICO.archive} size={14} /> Encerrar sessão
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Formulário: copiar pendências para sessão existente ou nova ──────────
function CopiarPendenciasForm({ sessaoId, sessoes, encerrarOrigem = true, onCreated, onCancel }) {
  const today = hojeFortaleza();
  const destinosExistentes = sessoes.filter(
    (sessao) => sessao.id !== sessaoId && ["a_iniciar", "em_andamento"].includes(sessao.situacao),
  );
  const [destinationMode, setDestinationMode] = useState(destinosExistentes.length ? "existing" : "new");
  const [destinationSessionId, setDestinationSessionId] = useState(destinosExistentes[0]?.id || "");
  const [form, setForm] = useState({ titulo: "", data_inicio: today, data_fim: "", data_reuniao: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const payload = destinationMode === "existing"
        ? { destination_mode: "existing", destination_session_id: Number(destinationSessionId) }
        : {
            destination_mode: "new",
            titulo: form.titulo,
            data_inicio: form.data_inicio,
            data_fim: form.data_fim || null,
            data_reuniao: form.data_reuniao || null,
          };
      const { data } = await api.post(`/pauta/sessoes/${sessaoId}/copy-pending`, payload);
      onCreated(data);
    } catch (ex) {
      setErr(ex.response?.data?.detail || "Falha ao copiar pendências.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="pauta-destination-switch" role="group" aria-label="Destino das pendências">
        <button type="button" className={destinationMode === "existing" ? "active" : ""}
          disabled={!destinosExistentes.length} onClick={() => setDestinationMode("existing")}>
          Sessão existente
        </button>
        <button type="button" className={destinationMode === "new" ? "active" : ""}
          onClick={() => setDestinationMode("new")}>
          Criar nova sessão
        </button>
      </div>

      {destinationMode === "existing" ? (
        <label className="field">
          <span>Sessão ativa de destino</span>
          <select required value={destinationSessionId}
            onChange={(e) => setDestinationSessionId(e.target.value)}>
            {destinosExistentes.map((sessao) => (
              <option key={sessao.id} value={sessao.id}>
                {sessao.titulo} · {SITUACAO_CFG[sessao.situacao]?.label} · {fmtData(sessao.data_inicio)}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <>
          <label className="field">
            <span>Título da nova sessão</span>
            <input type="text" required value={form.titulo}
              onChange={(e) => setForm((p) => ({ ...p, titulo: e.target.value }))}
              placeholder="ex: Pauta COPAG — Semana 10/06 a 14/06" />
          </label>
          <div className="pauta-copy-dates">
            <label className="field">
              <span>Início do período</span>
              <input type="date" required value={form.data_inicio}
                onChange={(e) => setForm((p) => ({ ...p, data_inicio: e.target.value }))} />
            </label>
            <label className="field">
              <span>Prazo da pauta</span>
              <input type="date" value={form.data_fim}
                onChange={(e) => setForm((p) => ({ ...p, data_fim: e.target.value }))} />
            </label>
            <label className="field">
              <span>Data da reunião</span>
              <input type="date" value={form.data_reuniao}
                onChange={(e) => setForm((p) => ({ ...p, data_reuniao: e.target.value }))} />
            </label>
          </div>
        </>
      )}
      <div className="pauta-copy-warning">
        {encerrarOrigem
          ? "A sessão atual será encerrada após a cópia bem-sucedida."
          : "O histórico da sessão de origem será preservado."}
      </div>
      {err && <div style={{ color: "#bf3535", fontSize: "0.85rem", fontWeight: 600 }}>{err}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="primary-button"
          disabled={saving || (destinationMode === "existing" && !destinationSessionId)}
          style={{ fontSize: "0.85rem", padding: "8px 18px" }}>
          {saving
            ? "Copiando..."
            : destinationMode === "existing"
              ? `${encerrarOrigem ? "Encerrar e copiar" : "Copiar"} para esta sessão`
              : `${encerrarOrigem ? "Encerrar e criar" : "Criar"} nova sessão`}
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
          <span>Prazo da pauta</span>
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
  const [prazo, setPrazo] = useState("");
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
        prazo: prazo || null,
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
            <span>Prazo dos processos</span>
            <input type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
          </label>
          <label className="field" style={{ flex: 2, minWidth: 200, margin: 0 }}>
            <span>Nota da gestão</span>
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
function PautaItemRow({ item, idx, isAdmin, onUpdated, onDelete }) {
  const [saving, setSaving] = useState(false);
  // Edição da nota da gestão (admin)
  const [editingGestao, setEditingGestao] = useState(false);
  const [notaGestao, setNotaGestao] = useState(item.nota_admin || "");
  // Edição do prazo (admin)
  const [editingPrazo, setEditingPrazo] = useState(false);
  const [prazo, setPrazo] = useState(item.prazo || "");

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

  async function saveNotaGestao() {
    setSaving(true);
    try {
      // string vazia limpa a nota; backend audita a mudança
      await api.patch(`/pauta/itens/${item.id}`, { nota_admin: notaGestao });
      setEditingGestao(false);
      onUpdated();
    } finally {
      setSaving(false);
    }
  }

  async function savePrazo() {
    setSaving(true);
    try {
      // null limpa o prazo; backend audita a mudança
      await api.patch(`/pauta/itens/${item.id}`, { prazo: prazo || null });
      setEditingPrazo(false);
      onUpdated();
    } finally {
      setSaving(false);
    }
  }

  const isActive = ["pendente", "em_acompanhamento"].includes(item.status);
  const statusColor = (STATUS_CFG[item.status] || STATUS_CFG.pendente).color;
  const atribuicaoDisplay = item.atribuicao_display ?? item.atribuicao;
  const canEditPrazo = isAdmin;

  return (
    <tr
      className="pauta-row-in"
      style={{
        opacity: item.status === "arquivado" ? .5 : 1,
        animationDelay: `${Math.min(idx ?? 0, 10) * 30}ms`,
      }}
    >
      <td style={{
        fontWeight: 600, fontSize: "0.78rem", color: "var(--primary)",
        borderLeft: `4px solid ${statusColor}`,
      }}>{item.protocolo}</td>
      <td>
        <span style={{ padding: "1px 7px", borderRadius: 8, fontSize: "0.72rem", fontWeight: 700, background: "var(--primary-light)", color: "var(--primary)" }}>
          {item.setor}
        </span>
      </td>
      {/* Atribuição atual no SEI (fallback histórico com marcador) */}
      <td style={{ fontSize: "0.78rem" }}>
        {atribuicaoDisplay ? (
          <span
            style={{ color: item.atribuicao_historica ? "var(--muted)" : "var(--ink)", fontStyle: item.atribuicao_historica ? "italic" : "normal" }}
            title={item.atribuicao_historica ? "Valor da inclusão na pauta — o processo já não consta no snapshot atual do setor" : undefined}
          >
            {atribuicaoDisplay}{item.atribuicao_historica && " *"}
          </span>
        ) : (
          <span style={{ color: "var(--muted)", fontStyle: "italic" }}>—</span>
        )}
      </td>
      <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>{item.tipo || "—"}</td>
      <td>
        <strong>{item.dias_no_setor_atual ?? item.dias_no_setor ?? "—"}</strong>
        {item.dias_no_setor_atual != null && item.dias_no_setor_atual !== item.dias_no_setor ? (
          <span title={`Na inclusão: ${item.dias_no_setor ?? "—"} dias`} style={{ marginLeft: 4, color: "var(--muted)", fontSize: "0.68rem" }}>*</span>
        ) : null}
      </td>
      <td><NivelBadge nivel={item.nivel_risco} /></td>
      <td style={{ fontSize: "0.78rem" }}>{item.assigned_to_nome || <span style={{ color: "var(--muted)", fontStyle: "italic" }}>Sem atribuição</span>}</td>
      <td className="pauta-status-column"><StatusBadge status={item.status} dataStatus={item.data_status} /></td>
      {/* Prazo — editável por admin */}
      <td style={{ fontSize: "0.78rem" }}>
        {editingPrazo ? (
          <div style={{ display: "flex", gap: 4 }}>
            <input type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)}
              style={{ padding: "3px 6px", borderRadius: 6, border: "1.5px solid var(--primary)", fontSize: "0.76rem" }} />
            <button type="button" className="table-button" disabled={saving} onClick={savePrazo}
              style={{ fontSize: "0.72rem", padding: "3px 8px" }}>✓</button>
            <button type="button" className="ghost-button" onClick={() => { setEditingPrazo(false); setPrazo(item.prazo || ""); }}
              style={{ fontSize: "0.72rem" }}>✕</button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ color: item.prazo ? "var(--ink)" : "var(--muted)", fontStyle: item.prazo ? "normal" : "italic" }}>
              {item.prazo ? fmtData(item.prazo) : "—"}
            </span>
            {canEditPrazo && (
              <button type="button" className="ghost-button" onClick={() => setEditingPrazo(true)}
                style={{ fontSize: "0.7rem", padding: "1px 6px" }} title="Editar prazo">✎</button>
            )}
          </div>
        )}
      </td>
      <td>{diasPrazoLabel(item.prazo, item.status)}</td>
      {/* Nota da gestão — editável apenas por admin */}
      <td style={{ fontSize: "0.78rem", maxWidth: 220 }}>
        {editingGestao ? (
          <div style={{ display: "flex", gap: 4 }}>
            <input type="text" value={notaGestao} onChange={(e) => setNotaGestao(e.target.value)}
              placeholder="Orientação da gestão"
              style={{ width: 170, padding: "3px 8px", borderRadius: 6, border: "1.5px solid var(--primary)", fontSize: "0.78rem" }} />
            <button type="button" className="table-button" disabled={saving} onClick={saveNotaGestao}
              style={{ fontSize: "0.72rem", padding: "3px 8px" }}>✓</button>
            <button type="button" className="ghost-button" onClick={() => { setEditingGestao(false); setNotaGestao(item.nota_admin || ""); }}
              style={{ fontSize: "0.72rem" }}>✕</button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ color: item.nota_admin ? "var(--ink)" : "var(--muted)", fontStyle: item.nota_admin ? "normal" : "italic" }}>
              {item.nota_admin || "—"}
            </span>
            {isAdmin && (
              <button type="button" className="ghost-button" onClick={() => setEditingGestao(true)}
                style={{ fontSize: "0.7rem", padding: "1px 6px" }} title="Editar nota da gestão">✎</button>
            )}
          </div>
        )}
      </td>
      <td>
        <div style={{ display: "flex", gap: 4, flexWrap: "nowrap" }}>
          {/* Forçar resolução: exclusivo do admin, com confirmação */}
          {isAdmin && isActive && (
            <button type="button" className="table-button" disabled={saving}
              onClick={() => {
                if (window.confirm("Este processo ainda pode constar no setor.\nDeseja encerrar manualmente na pauta mesmo assim?")) {
                  handleStatusChange("resolvido_manual");
                }
              }}
              style={{ fontSize: "0.7rem", padding: "3px 8px", color: "var(--muted)", borderColor: "var(--border)" }}
              title="Encerrar manualmente — a resolução normalmente é detectada automaticamente via snapshot">
              Forçar resolução
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
  const [showEncerrarModal, setShowEncerrarModal] = useState(false);
  const [showEditarSessao, setShowEditarSessao] = useState(false);
  const [showMetricas, setShowMetricas] = useState(false);
  const [metricas, setMetricas] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [sort, setSort] = useState({ key: "score_risco", dir: "desc" });

  const itens = sessaoData?.itens || [];
  const sortedItens = useMemo(() => sortPautaItems(itens, sort), [itens, sort]);

  function handleSort(column) {
    setSort((current) => current.key === column
      ? { key: column, dir: current.dir === "asc" ? "desc" : "asc" }
      : { key: column, dir: PAUTA_SORT_DEFAULT[column] || "asc" });
  }

  async function loadMetricas() {
    if (!user?.is_admin) return;
    try {
      const { data } = await api.get("/pauta/metricas");
      setMetricas(data);
    } catch {
      // silencioso
    }
  }

  async function handleEncerrarSessao(copiarPendencias) {
    if (copiarPendencias) {
      // "Encerrar e copiar" → o copy-pending encerra a origem atomicamente
      setShowEncerrarModal(false);
      setShowCopiarForm(true);
      return;
    }

    try {
      await api.patch(`/pauta/sessoes/${sessaoAtual}`, { ativa: false });
      setShowEncerrarModal(false);
      setMsg("✓ Sessão encerrada.");
      await loadSessoes();
      await loadMetricas();
    } catch (err) {
      setMsg(`✗ ${err.response?.data?.detail || "falha ao encerrar sessão"}`);
      setShowEncerrarModal(false);
    }
  }

  async function handleGerarPdf() {
    if (!sessaoData) return;
    setPdfLoading(true);
    try {
      generatePautaPdf({ ...sessaoData, itens: sortedItens });
    } finally {
      setPdfLoading(false);
    }
  }

  async function loadSessoes(preferredId = sessaoAtual) {
    try {
      const { data } = await api.get("/pauta/sessoes", { params: { ativa: true } });
      setSessoes(data);
      if (data.length === 0) {
        setSessaoAtual(null);
        setSessaoData(null);
      } else if (!preferredId || !data.some((s) => s.id === preferredId)) {
        setSessaoAtual(data[0].id);
      }
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
      loadMetricas();
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
  const totalAtivos = (contagens.pendente || 0) + (contagens.em_acompanhamento || 0);
  const totalResolvidos = (contagens.saiu_do_setor || 0) + (contagens.resolvido_manual || 0);
  // Sessão operável (adicionar/encerrar/copiar): apenas a_iniciar ou em_andamento
  const sessaoOperavel = ["a_iniciar", "em_andamento"].includes(sessaoData?.situacao);
  const temPendencias = (contagens.pendente || 0) + (contagens.em_acompanhamento || 0) > 0;

  return (
    <div className="page-grid">
      {/* Hero contextual: nome da sessão ativa + estado do prazo */}
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Pauta Prioritária</p>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0 }}>{sessaoData?.titulo || "Pauta Prioritária"}</h1>
            {sessaoData?.situacao && (
              <SituacaoBadge situacao={sessaoData.situacao} label={sessaoData.situacao_label} />
            )}
          </div>
          <p>
            {sessaoData
              ? `${prazoInfo(sessaoData.data_fim, totalAtivos).label}${sessaoData.data_fim ? ` · prazo ${fmtData(sessaoData.data_fim)}` : ""}`
              : "Processos críticos selecionados para acompanhamento semanal."}
          </p>
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
                <option key={s.id} value={s.id}>
                  {s.titulo} · {(SITUACAO_CFG[s.situacao]?.label || "").toUpperCase()}
                </option>
              ))}
              {sessoes.length === 0 && <option value="">Nenhuma sessão ativa</option>}
            </select>
          </label>
          {user?.is_admin && (
            <>
              <button type="button" className="ghost-button" onClick={() => setShowNovaSessao(true)}
                style={{ fontSize: "0.82rem", padding: "8px 14px", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <LucideIcon paths={ICO.plus} size={14} /> Nova sessão
              </button>
              {sessaoAtual && sessaoData && (
                <>
                  {/* Ação primária — só em sessão operável */}
                  {sessaoOperavel && (
                    <button type="button" className="primary-button" onClick={() => setShowAdicionarModal(true)}
                      style={{ fontSize: "0.82rem", padding: "8px 16px", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <LucideIcon paths={ICO.plus} size={14} /> Adicionar processos
                    </button>
                  )}
                  {/* Secundárias */}
                  <button type="button" className="table-button"
                    onClick={handleGerarPdf} disabled={pdfLoading}
                    style={{ fontSize: "0.82rem", padding: "8px 14px", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 6 }}
                    title="Exportar PDF da pauta desta sessão">
                    <LucideIcon paths={ICO.fileDown} size={14} /> {pdfLoading ? "Gerando..." : "PDF"}
                  </button>
                  {/* Administrativas: menu ⋯ — Editar/Encerrar apenas se operável */}
                  <AdminMenu
                    sessaoOperavel={sessaoOperavel}
                    temPendencias={temPendencias}
                    onEditar={() => setShowEditarSessao(true)}
                    onEncerrar={() => setShowEncerrarModal(true)}
                    onCopiar={() => setShowCopiarForm(true)}
                  />
                </>
              )}
            </>
          )}
          {!user?.is_admin && sessaoData && (
            <button type="button" className="table-button"
              onClick={handleGerarPdf} disabled={pdfLoading}
              style={{ fontSize: "0.82rem", padding: "8px 14px", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 6 }}
              title="Exportar PDF da minha pauta">
              <LucideIcon paths={ICO.fileDown} size={14} /> {pdfLoading ? "Gerando..." : "PDF"}
            </button>
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

      {/* Cronograma da sessão — visível para todos os perfis */}
      {sessaoData && (
        <section className="panel" style={{ padding: "16px 20px" }}>
          <CronogramaSessao
            sessao={sessaoData}
            totalAtivos={totalAtivos}
            isAdmin={Boolean(user?.is_admin)}
            onEditar={() => setShowEditarSessao(true)}
          />
          {showEditarSessao && user?.is_admin && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
              <SessaoEditForm
                sessao={sessaoData}
                onSaved={() => {
                  setShowEditarSessao(false);
                  setMsg("✓ Sessão atualizada.");
                  loadSessaoData(sessaoAtual);
                  loadSessoes();
                }}
                onCancel={() => setShowEditarSessao(false)}
              />
            </div>
          )}
          <ProgressoResolucao contagens={contagens} />
        </section>
      )}

      {/* Modal: encerrar sessão */}
      {showEncerrarModal && sessaoData && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
        }} onClick={() => setShowEncerrarModal(false)}>
          <div style={{
            background: "var(--panel)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)",
            boxShadow: "0 16px 48px rgba(0,0,0,.25)", width: "100%", maxWidth: 480, padding: 28,
          }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 6px", color: "var(--ink)" }}>Encerrar sessão</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: 18 }}>
              <strong>{sessaoData.titulo}</strong>
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 20 }}>
              {[
                { label: "Resolvidos", value: (sessaoData.contagens?.saiu_do_setor || 0) + (sessaoData.contagens?.resolvido_manual || 0), color: "#1a7a50" },
                { label: "Pendentes", value: (sessaoData.contagens?.pendente || 0) + (sessaoData.contagens?.em_acompanhamento || 0), color: "#8a5b00" },
                { label: "Total", value: sessaoData.itens?.length || 0, color: "var(--primary)" },
              ].map((kpi) => (
                <div key={kpi.label} style={{ textAlign: "center", padding: "12px 8px", borderRadius: 8, background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <strong style={{ display: "block", fontSize: "1.5rem", fontWeight: 800, color: kpi.color, lineHeight: 1 }}>{kpi.value}</strong>
                  <small style={{ fontSize: "0.72rem", color: "var(--muted)", fontWeight: 700, textTransform: "uppercase" }}>{kpi.label}</small>
                </div>
              ))}
            </div>

            {((sessaoData.contagens?.pendente || 0) + (sessaoData.contagens?.em_acompanhamento || 0)) > 0 && (
              <div style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(254,187,18,.12)", border: "1px solid rgba(254,187,18,.3)", marginBottom: 18, fontSize: "0.82rem", color: "#8a5b00", fontWeight: 600 }}>
                ⚠ {(sessaoData.contagens?.pendente || 0) + (sessaoData.contagens?.em_acompanhamento || 0)} processo(s) ainda pendente(s). Você poderá copiá-los para uma sessão ativa ou criar uma nova.
              </div>
            )}

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {((sessaoData.contagens?.pendente || 0) + (sessaoData.contagens?.em_acompanhamento || 0)) > 0 && (
                <button type="button" className="primary-button"
                  onClick={() => handleEncerrarSessao(true)}
                  style={{ fontSize: "0.85rem", padding: "9px 16px" }}>
                  Encerrar e copiar pendências
                </button>
              )}
              <button type="button" className="table-button"
                onClick={() => handleEncerrarSessao(false)}
                style={{ fontSize: "0.85rem", padding: "9px 16px" }}>
                Encerrar sem copiar
              </button>
              <button type="button" className="ghost-button" onClick={() => setShowEncerrarModal(false)}
                style={{ fontSize: "0.85rem" }}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Formulário: copiar pendências para nova sessão */}
      {showCopiarForm && sessaoAtual && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3>{sessaoOperavel ? "Encerrar sessão e copiar pendências" : "Copiar pendências"}</h3>
              <p>
                {sessaoOperavel ? "Encerra a sessão atual e copia" : "Copia"} seus processos{" "}
                <strong>Pendente</strong> e <strong>Em acompanhamento</strong> para uma sessão ativa ou nova.
                O histórico da sessão original é preservado.
              </p>
            </div>
          </div>
          <CopiarPendenciasForm
            sessaoId={sessaoAtual}
            sessoes={sessoes}
            encerrarOrigem={sessaoOperavel}
            onCreated={async (nova) => {
              setShowCopiarForm(false);
              const ignor = nova.ignorados ? ` · ${nova.ignorados} já existente(s) no destino ou em outra pauta` : "";
              const prefixo = sessaoOperavel
                ? "Sessão anterior encerrada e"
                : "Pendências";
              setMsg(`✓ ${prefixo} ${nova.itens_copiados} item(s) copiado(s) para "${nova.titulo}"${ignor}.`);
              await loadSessoes(nova.sessao_destino_id);
              setSessaoAtual(nova.sessao_destino_id);
              await loadMetricas();
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
              </h3>
              <p>
                {itens.length} processo{itens.length !== 1 ? "s" : ""} · {totalAtivos} ativo{totalAtivos !== 1 ? "s" : ""} · {totalResolvidos} resolvido{totalResolvidos !== 1 ? "s" : ""}
                {sessaoData?.observacoes && <span> · {sessaoData.observacoes}</span>}
              </p>
            </div>
          </div>

          {/* Aviso de resolução automática — visível apenas para responsáveis (não-admin) */}
          {!user?.is_admin && totalAtivos > 0 && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8, padding: "8px 14px",
              borderRadius: 8, marginBottom: 12,
              background: "rgba(39,49,104,.06)", border: "1px solid rgba(39,49,104,.15)",
              fontSize: "0.78rem", color: "var(--muted)",
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, color: "var(--primary)" }}>
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              A resolução é detectada automaticamente quando o processo deixar de constar no snapshot do setor.
            </div>
          )}

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
              <table className="data-table pauta-items-table" style={{ fontSize: "0.82rem", minWidth: 1120 }}>
                <thead>
                  <tr>
                    <SortablePautaHeader column="protocolo" sort={sort} onSort={handleSort}>Protocolo</SortablePautaHeader>
                    <SortablePautaHeader column="setor" sort={sort} onSort={handleSort}>Setor</SortablePautaHeader>
                    <SortablePautaHeader column="atribuicao" sort={sort} onSort={handleSort}>Atribuição</SortablePautaHeader>
                    <SortablePautaHeader column="tipo" sort={sort} onSort={handleSort}>Tipo</SortablePautaHeader>
                    <SortablePautaHeader column="dias_no_setor" sort={sort} onSort={handleSort}>Dias</SortablePautaHeader>
                    <SortablePautaHeader column="score_risco" sort={sort} onSort={handleSort}>Risco</SortablePautaHeader>
                    <SortablePautaHeader column="responsavel" sort={sort} onSort={handleSort}>Responsável</SortablePautaHeader>
                    <SortablePautaHeader column="status" sort={sort} onSort={handleSort} className="pauta-status-column">Status</SortablePautaHeader>
                    <SortablePautaHeader column="prazo" sort={sort} onSort={handleSort}>Prazo</SortablePautaHeader>
                    <SortablePautaHeader column="dias_prazo" sort={sort} onSort={handleSort}>Dias prazo</SortablePautaHeader>
                    <SortablePautaHeader column="nota_admin" sort={sort} onSort={handleSort}>Nota gestão</SortablePautaHeader>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedItens.map((item, idx) => (
                    <PautaItemRow
                      key={item.id}
                      item={item}
                      idx={idx}
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

      {/* Painel de métricas (admin, colapsável) */}
      {user?.is_admin && metricas && (
        <section className="panel">
          <button type="button" onClick={() => setShowMetricas((v) => !v)}
            style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit", padding: 0 }}>
            <h3 style={{ margin: 0, color: "var(--ink)", fontSize: "1rem" }}>Métricas de eficiência</h3>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)", marginLeft: "auto" }}>{showMetricas ? "▲ Recolher" : "▼ Expandir"}</span>
          </button>

          {showMetricas && (
            <div style={{ marginTop: 16 }}>
              {/* KPIs globais */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
                {[
                  { label: "Tempo médio até resolução automática", value: metricas.tempo_medio_auto_dias != null ? `${metricas.tempo_medio_auto_dias}d` : "—", hint: "Apenas saiu_do_setor" },
                  { label: "Overrides manuais (histórico)", value: metricas.overrides_manuais_total, hint: "resolvido_manual, admin only" },
                  { label: "Pendências arrastadas", value: metricas.pendencias_arrastadas, hint: "Itens ativos em sessões encerradas" },
                ].map((kpi) => (
                  <div key={kpi.label} style={{ padding: 14, borderRadius: 10, background: "var(--bg)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--primary)", lineHeight: 1 }}>{kpi.value}</div>
                    <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--ink)", marginTop: 4 }}>{kpi.label}</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--muted)", marginTop: 2 }}>{kpi.hint}</div>
                  </div>
                ))}
              </div>

              {/* Eficiência por sessão */}
              <p style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: ".05em" }}>
                Eficiência por sessão (últimas {metricas.sessoes?.length})
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {(metricas.sessoes || []).map((s) => (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--muted)", minWidth: 180, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                      title={s.titulo}>{s.titulo}</span>
                    <div style={{ flex: 1, height: 12, borderRadius: 999, background: "var(--primary-light)", overflow: "hidden", position: "relative" }}>
                      <div style={{ height: "100%", width: `${s.taxa_auto_pct}%`, background: "#1a7a50", borderRadius: 999 }} />
                      {s.resolvidos_manual > 0 && (
                        <div style={{ position: "absolute", top: 0, left: `${s.taxa_auto_pct}%`, height: "100%", width: `${Math.round(s.resolvidos_manual / s.total * 100)}%`, background: "#4ade80", opacity: .6 }} />
                      )}
                    </div>
                    <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "#1a7a50", minWidth: 36, textAlign: "right" }}>{s.taxa_auto_pct}%</span>
                    <span style={{ fontSize: "0.7rem", color: "var(--muted)", minWidth: 60 }}>{s.resolvidos_auto}/{s.total} auto</span>
                    {!s.ativa && <span style={{ fontSize: "0.65rem", color: "var(--muted)", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px" }}>encerrada</span>}
                  </div>
                ))}
              </div>
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
