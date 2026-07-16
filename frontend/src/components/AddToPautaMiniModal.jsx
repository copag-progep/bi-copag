import { useEffect, useState } from "react";
import api from "../api/client";

/**
 * Mini-modal para adicionar um processo específico à pauta.
 * Usado em /risco e /atribuicoes.
 *
 * Props:
 *   processo: { protocolo, setor, entrada_setor?, atribuicao?, tipo?, dias_no_setor?, score?, nivel? }
 *   onClose: () => void
 *   onAdded: () => void
 */
export default function AddToPautaMiniModal({ processo, onClose, onAdded }) {
  const [sessoes, setSessoes] = useState([]);
  const [users, setUsers] = useState([]);
  const [sessaoId, setSessaoId] = useState("");
  const [assignTo, setAssignTo] = useState("");
  const [nota, setNota] = useState("");
  const [prazo, setPrazo] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/pauta/sessoes", { params: { ativa: true } }),
      api.get("/admin/users"),
    ]).then(([s, u]) => {
      // Apenas sessões elegíveis (a iniciar / em andamento) recebem processos
      const elegiveis = s.data.filter((x) => x.situacao === "a_iniciar" || x.situacao === "em_andamento");
      setSessoes(elegiveis);
      if (elegiveis.length > 0) setSessaoId(elegiveis[0].id);
      setUsers(
        u.data.filter((usr) =>
          !usr.is_admin &&
          Array.isArray(usr.setores) &&
          usr.setores.includes(processo.setor)
        )
      );
    }).catch(() => {});
  }, [processo.setor]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!sessaoId) { setErr("Selecione uma sessão."); return; }
    setSaving(true);
    setErr("");
    try {
      await api.post(`/pauta/sessoes/${sessaoId}/itens`, {
        protocolo: processo.protocolo,
        setor: processo.setor,
        entrada_setor: processo.entrada_setor || null,
        prazo: prazo || null,
        atribuicao: processo.atribuicao || null,
        tipo: processo.tipo || null,
        dias_no_setor: processo.dias_no_setor ?? processo.dias_com_atribuicao ?? null,
        score_risco: processo.score ?? null,
        nivel_risco: processo.nivel ?? null,
        assigned_to: assignTo ? Number(assignTo) : null,
        nota_admin: nota || null,
      });
      onAdded();
    } catch (ex) {
      setErr(ex.response?.data?.detail || "Processo já incluído nesta sessão.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
    }} onClick={onClose}>
      <form onSubmit={handleSubmit}
        style={{
          background: "var(--panel)", borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border)", boxShadow: "0 16px 48px rgba(0,0,0,.25)",
          width: "100%", maxWidth: 480, padding: 24, display: "flex", flexDirection: "column", gap: 14,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--ink)" }}>Adicionar à Pauta</h3>
            <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--muted)" }}>
              <code style={{ color: "var(--primary)", fontWeight: 700 }}>{processo.protocolo}</code>
              {" · "}{processo.setor}
              {processo.dias_no_setor != null && ` · ${processo.dias_no_setor}d`}
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={onClose} style={{ fontSize: "1.1rem", padding: "2px 8px" }}>✕</button>
        </div>

        <label className="field" style={{ margin: 0 }}>
          <span>Sessão</span>
          <select value={sessaoId} onChange={(e) => setSessaoId(e.target.value)} required>
            {sessoes.length === 0
              ? <option value="">Nenhuma sessão ativa</option>
              : sessoes.map((s) => <option key={s.id} value={s.id}>{s.titulo}</option>)
            }
          </select>
        </label>

        <label className="field" style={{ margin: 0 }}>
          <span>Atribuir ao responsável (opcional)</span>
          <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)}>
            <option value="">Sem atribuição por agora</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            {users.length === 0 && <option value="" disabled>Nenhum usuário com acesso a {processo.setor}</option>}
          </select>
        </label>

        <label className="field" style={{ margin: 0 }}>
          <span>Prazo do processo (opcional)</span>
          <input type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
        </label>

        <label className="field" style={{ margin: 0 }}>
          <span>Nota da gestão (opcional)</span>
          <input type="text" value={nota} onChange={(e) => setNota(e.target.value)}
            placeholder="Orientação ou urgência" />
        </label>

        {err && <div style={{ color: "#bf3535", fontSize: "0.82rem", fontWeight: 600 }}>{err}</div>}

        <div style={{ display: "flex", gap: 8 }}>
          <button type="submit" className="primary-button" disabled={saving || sessoes.length === 0}
            style={{ fontSize: "0.85rem", padding: "9px 18px" }}>
            {saving ? "Adicionando..." : "Adicionar à pauta"}
          </button>
          <button type="button" className="ghost-button" onClick={onClose} style={{ fontSize: "0.85rem" }}>
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
