import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/AuthContext";
import { normalizeUploadsPayload } from "../utils/uploadsPayload";


function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function formatDateTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value
    : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(d);
}

const ACTION_LABELS = {
  "upload.imported":    { label: "Upload importado",         color: "var(--success)" },
  "upload.replaced":    { label: "Upload substituído",       color: "#9a6c00" },
  "upload.excluido":    { label: "Upload excluído",          color: "var(--danger)" },
  "upload.data_alterada":{ label: "Data do upload alterada", color: "var(--primary)" },
  "usuario.criado":     { label: "Usuário criado",           color: "var(--success)" },
  "usuario.excluido":   { label: "Usuário excluído",         color: "var(--danger)" },
  "senha.alterada":     { label: "Senha alterada",           color: "var(--primary)" },
  "sei_usuario.criado": { label: "DE-PARA criado",           color: "var(--success)" },
  "sei_usuario.editado": { label: "DE-PARA editado",         color: "var(--primary)" },
  "sei_usuario.excluido":{ label: "DE-PARA excluído",        color: "var(--danger)" },
  "sei_usuario.importado":{ label: "DE-PARA importado",      color: "var(--primary)" },
  "sei_usuario.alias_adicionado":{ label: "Alias SEI adicionado", color: "var(--success)" },
  "sei_usuario.alias_removido":{ label: "Alias SEI removido", color: "var(--danger)" },
  "sei_usuario.unificado":{ label: "Histórico SEI unificado", color: "var(--accent-dark)" },
  "process_type_weight.salvo":   { label: "Peso de tipo salvo",    color: "var(--primary)" },
  "process_type_weight.removido":{ label: "Peso de tipo removido", color: "var(--danger)" },
};

function ActionBadge({ action }) {
  const cfg = ACTION_LABELS[action] || { label: action, color: "var(--muted)" };
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 999, fontSize: "0.75rem", fontWeight: 700,
      background: `${cfg.color}18`, color: cfg.color, whiteSpace: "nowrap",
    }}>
      {cfg.label}
    </span>
  );
}

const IcoUsers = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>
  </svg>
);
const IcoCloud = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
    <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/>
  </svg>
);
const IcoLog = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
);

function parseDetails(raw) {
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    return Object.entries(obj).map(([k, v]) => `${k}: ${v}`).join(" · ");
  } catch {
    return raw;
  }
}


export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditTotalPages, setAuditTotalPages] = useState(1);
  const [auditLoading, setAuditLoading] = useState(false);
  const AUDIT_PAGE_SIZE = 50;

  // ── Pesos por tipo ──────────────────────────────────────────────────────
  const [typeWeights, setTypeWeights] = useState([]);
  const [twLoading, setTwLoading] = useState(false);
  const [twSearch, setTwSearch] = useState("");
  const [twFilter, setTwFilter] = useState("todos"); // todos | configurados | modificados
  const [twEditing, setTwEditing] = useState(null); // { tipo, peso, categoria, justificativa, id }
  const [twSaving, setTwSaving] = useState(false);
  const [twMsg, setTwMsg] = useState("");

  async function loadTypeWeights() {
    setTwLoading(true);
    try {
      const { data } = await api.get("/admin/type-weights");
      setTypeWeights(data);
    } catch {
      // silencioso — seção fica vazia
    } finally {
      setTwLoading(false);
    }
  }

  async function saveTypeWeight(row) {
    setTwSaving(true);
    setTwMsg("");
    try {
      await api.put("/admin/type-weights", {
        tipo: row.tipo,
        peso: Number(row.peso),
        categoria: row.categoria || null,
        justificativa: row.justificativa || null,
        ativo: row.ativo !== false,
      });
      setTwMsg(`✓ Peso de "${row.tipo}" salvo.`);
      setTwEditing(null);
      await loadTypeWeights();
    } catch (err) {
      setTwMsg(`✗ Erro: ${err.response?.data?.detail || "falha ao salvar"}`);
    } finally {
      setTwSaving(false);
    }
  }

  async function removeTypeWeight(id, tipo) {
    if (!window.confirm(`Remover peso de "${tipo}"? O tipo voltará ao padrão 1.00.`)) return;
    try {
      await api.delete(`/admin/type-weights/${id}`);
      setTwMsg(`✓ Peso de "${tipo}" removido.`);
      await loadTypeWeights();
    } catch (err) {
      setTwMsg(`✗ ${err.response?.data?.detail || "falha ao remover"}`);
    }
  }
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    is_admin: false,
  });

  if (!user?.is_admin) {
    return <div className="alert error">Acesso restrito a administradores.</div>;
  }

  async function loadAdminData() {
    setLoading(true);
    setError("");
    try {
      const [usersResponse, uploadsResponse] = await Promise.all([
        api.get("/admin/users"),
        api.get("/uploads", { params: { page: 1, page_size: 30 } }),
      ]);
      setUsers(usersResponse.data);
      setUploads(normalizeUploadsPayload(uploadsResponse.data).items);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar dados administrativos.");
    } finally {
      setLoading(false);
    }
  }

  async function loadAuditLogs(page = auditPage) {
    setAuditLoading(true);
    try {
      const { data } = await api.get("/admin/audit-logs", {
        params: { page, page_size: AUDIT_PAGE_SIZE },
      });
      setAuditLogs(data.items || []);
      setAuditTotal(data.total || 0);
      setAuditTotalPages(data.total_pages || 1);
    } catch {
      // silencia — log é secundário
    } finally {
      setAuditLoading(false);
    }
  }

  useEffect(() => {
    loadAdminData();
    loadAuditLogs(1);
    loadTypeWeights();
  }, []);

  useEffect(() => {
    loadAuditLogs(auditPage);
  }, [auditPage]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.post("/admin/users", form);
      setMessage("Usuário criado com sucesso.");
      setForm({ name: "", email: "", password: "", is_admin: false });
      await loadAdminData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível criar o usuário.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteUser(targetUser) {
    const confirmed = window.confirm(`Deseja excluir o usuário ${targetUser.name}?`);
    if (!confirmed) {
      return;
    }

    setDeletingUserId(targetUser.id);
    setMessage("");
    setError("");
    try {
      const { data } = await api.delete(`/admin/users/${targetUser.id}`);
      setMessage(data.message || "Usuário excluído com sucesso.");
      await loadAdminData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível excluir o usuário.");
    } finally {
      setDeletingUserId(null);
    }
  }

  return (
    <div className="page-grid">
      <section className="hero-panel ms-hero">
        <div className="ms-hero-body">
          <p className="eyebrow">Administração</p>
          <h1>Gestão de acessos e histórico</h1>
          <p className="ms-hero-sub">
            Crie novos logins, acompanhe os snapshots mais recentes e monitore o log de auditoria.
          </p>
        </div>
        <div className="ms-hero-kpi">
          <span className="ms-hero-kpi-value">{loading ? "—" : users.length}</span>
          <span className="ms-hero-kpi-label">usuários ativos</span>
        </div>
      </section>

      <section className="stats-grid stats-grid-3">
        <StatCard
          icon={<IcoUsers />}
          label="Usuários cadastrados"
          value={loading ? "—" : users.length}
          hint={loading ? undefined : `${users.filter(u => u.is_admin).length} administrador${users.filter(u => u.is_admin).length !== 1 ? "es" : ""}`}
        />
        <StatCard
          icon={<IcoCloud />}
          label="Snapshots importados"
          value={loading ? "—" : uploads.length}
          hint="Últimos 30 registros"
        />
        <StatCard
          icon={<IcoLog />}
          label="Eventos de auditoria"
          value={auditLoading && auditTotal === 0 ? "—" : auditTotal}
          hint="Total registrado"
        />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Novo usuário</h3>
            <p>Cadastre contas e defina se o novo acesso terá privilégios administrativos.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nome</span>
            <input
              type="text"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
            />
          </label>

          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              required
            />
          </label>

          <label className="field">
            <span>Senha</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              required
            />
          </label>

          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={form.is_admin}
              onChange={(event) => setForm((current) => ({ ...current, is_admin: event.target.checked }))}
            />
            <span>Conceder acesso de administrador</span>
          </label>

          {message ? <div className="alert success full-width">{message}</div> : null}
          {error ? <div className="alert error full-width">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? "Salvando..." : "Criar usuário"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Usuários cadastrados</h3>
            <p>Contas disponíveis para autenticação na aplicação.</p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando usuários..." />
        ) : (
          <DataTable
            columns={[
              { key: "name", label: "Nome" },
              { key: "email", label: "Email" },
              {
                key: "is_admin",
                label: "Perfil",
                render: (value) => (value ? "Administrador" : "Usuário"),
              },
              { key: "created_at", label: "Criado em" },
              ...(user?.is_admin
                ? [
                    {
                      key: "actions",
                      label: "Ações",
                      render: (_, row) =>
                        row.id === user.id ? (
                          <span className="table-helper">Conta atual</span>
                        ) : (
                          <button
                            type="button"
                            className="table-button danger"
                            onClick={() => handleDeleteUser(row)}
                            disabled={deletingUserId === row.id}
                          >
                            {deletingUserId === row.id ? "Excluindo..." : "Excluir"}
                          </button>
                        ),
                    },
                  ]
                : []),
            ]}
            rows={users}
          />
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Últimos uploads</h3>
            <p>
              Referência rápida dos 30 snapshots mais recentes. Para gerenciar todos, acesse{" "}
              <a href="/enviar-relatorio" style={{ color: "var(--accent)", fontWeight: 700 }}>
                Enviar Relatório
              </a>
              .
            </p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando histórico..." />
        ) : (
          <DataTable
            columns={[
              { key: "setor", label: "Setor" },
              {
                key: "data_relatorio",
                label: "Data do relatório",
                render: (value) => formatDate(value),
              },
              { key: "original_filename", label: "Arquivo" },
              { key: "total_records", label: "Registros" },
            ]}
            rows={uploads}
            emptyMessage="Nenhum upload encontrado."
          />
        )}
      </section>

      {/* Log de auditoria */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Log de auditoria</h3>
            <p>Registro das ações críticas realizadas no sistema — uploads, exclusões, criação de usuários e alterações de senha.</p>
          </div>
          <button type="button" className="ghost-button"
            onClick={() => { setAuditPage(1); loadAuditLogs(1); }}
            style={{ padding: "8px 14px", fontSize: "0.82rem" }}>
            Atualizar
          </button>
        </div>
        {auditLoading ? (
          <LoadingBlock label="Carregando log..." />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ whiteSpace: "nowrap" }}>Data / Hora</th>
                    <th>Usuário</th>
                    <th>Ação</th>
                    <th>Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={4} style={{ textAlign: "center", color: "var(--muted)", padding: "24px" }}>
                        Nenhum registro de auditoria encontrado.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id}>
                        <td style={{ fontSize: "0.78rem", whiteSpace: "nowrap", color: "var(--muted)" }}>
                          {formatDateTime(log.created_at)}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, fontSize: "0.82rem" }}>{log.user_name}</div>
                          <div style={{ fontSize: "0.72rem", color: "var(--muted)" }}>{log.user_email}</div>
                        </td>
                        <td><ActionBadge action={log.action} /></td>
                        <td style={{ fontSize: "0.78rem", color: "var(--muted)", maxWidth: 320 }}>
                          {parseDetails(log.details) || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="pagination-bar">
              <span className="pagination-summary">
                Página {auditPage} de {auditTotalPages} | {auditTotal} registros
              </span>
              <div className="table-actions">
                <button type="button" className="table-button"
                  disabled={auditPage === 1}
                  onClick={() => setAuditPage((p) => Math.max(1, p - 1))}>
                  Anterior
                </button>
                <button type="button" className="table-button"
                  disabled={auditPage === auditTotalPages}
                  onClick={() => setAuditPage((p) => Math.min(auditTotalPages, p + 1))}>
                  Próxima
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {/* ── Pesos por Tipo de Processo ─────────────────────────────────── */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Pesos por Tipo de Processo</h3>
            <p>
              Define o multiplicador de prioridade no Score de Risco por tipo.
              Tipos sem configuração usam peso padrão 1,00 (neutro).
              Novos tipos que entrarem via upload aparecem automaticamente.
            </p>
          </div>
          <button
            type="button"
            className="table-button"
            onClick={loadTypeWeights}
            disabled={twLoading}
          >
            {twLoading ? "Carregando..." : "↻ Atualizar lista"}
          </button>
        </div>

        {twMsg && (
          <div style={{
            padding: "8px 14px", borderRadius: 8, marginBottom: 12,
            background: twMsg.startsWith("✓") ? "rgba(26,122,80,.1)" : "rgba(191,53,53,.1)",
            color: twMsg.startsWith("✓") ? "#1a7a50" : "#bf3535",
            fontSize: "0.85rem", fontWeight: 600,
          }}>
            {twMsg}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
          <input
            type="text"
            placeholder="Buscar tipo..."
            value={twSearch}
            onChange={(e) => setTwSearch(e.target.value)}
            style={{
              flex: 1, minWidth: 200, border: "1.5px solid var(--border-strong)",
              borderRadius: 999, padding: "7px 14px", fontSize: "0.82rem",
              fontFamily: "inherit", color: "var(--ink)", background: "var(--bg)",
            }}
          />
          {["todos", "configurados", "modificados"].map((f) => (
            <button
              key={f}
              type="button"
              className={`risk-filter-pill ${twFilter === f ? "active" : ""}`}
              onClick={() => setTwFilter(f)}
              style={{ textTransform: "capitalize" }}
            >
              {f === "todos" ? `Todos (${typeWeights.length})`
                : f === "configurados" ? `Configurados (${typeWeights.filter((t) => t.configurado).length})`
                : `Modificados (${typeWeights.filter((t) => t.configurado && t.peso !== 1.0).length})`}
            </button>
          ))}
        </div>

        {twLoading ? (
          <LoadingBlock label="Carregando tipos..." />
        ) : (
          <div className="table-shell">
            <table className="data-table" style={{ fontSize: "0.82rem" }}>
              <thead>
                <tr>
                  <th>Tipo de processo</th>
                  <th style={{ width: 80 }}>Processos</th>
                  <th style={{ width: 80 }}>Peso</th>
                  <th>Categoria</th>
                  <th style={{ width: 110 }}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {typeWeights
                  .filter((t) => {
                    const matchSearch = !twSearch || t.tipo.toLowerCase().includes(twSearch.toLowerCase());
                    const matchFilter =
                      twFilter === "todos" ||
                      (twFilter === "configurados" && t.configurado) ||
                      (twFilter === "modificados" && t.configurado && t.peso !== 1.0);
                    return matchSearch && matchFilter;
                  })
                  .map((t) => {
                    const isEditing = twEditing?.tipo === t.tipo;
                    const pesoColor =
                      t.peso > 1.1 ? "#1a7a50" :
                      t.peso > 1.0 ? "#8a5b00" :
                      t.peso < 1.0 ? "#bf3535" : "var(--muted)";

                    return (
                      <tr key={t.tipo}>
                        <td style={{ maxWidth: 400, wordBreak: "break-word" }}>
                          {t.tipo}
                          {t.configurado && (
                            <span style={{
                              marginLeft: 8, padding: "1px 7px", borderRadius: 8,
                              fontSize: "0.68rem", fontWeight: 700,
                              background: "rgba(39,49,104,.08)", color: "var(--primary)",
                            }}>
                              configurado
                            </span>
                          )}
                        </td>
                        <td style={{ color: "var(--muted)", fontSize: "0.78rem", textAlign: "right" }}>
                          {t.total_processos?.toLocaleString("pt-BR") || "—"}
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="number"
                              step="0.05"
                              min="0.80"
                              max="1.50"
                              value={twEditing.peso}
                              onChange={(e) => setTwEditing((prev) => ({ ...prev, peso: e.target.value }))}
                              style={{
                                width: 70, padding: "4px 8px", borderRadius: 6,
                                border: "1.5px solid var(--primary)", fontSize: "0.82rem",
                              }}
                            />
                          ) : (
                            <span style={{ fontWeight: 700, color: pesoColor }}>
                              {t.peso.toFixed(2)}×
                            </span>
                          )}
                        </td>
                        <td>
                          {isEditing ? (
                            <input
                              type="text"
                              placeholder="ex: Alta prioridade"
                              value={twEditing.categoria || ""}
                              onChange={(e) => setTwEditing((prev) => ({ ...prev, categoria: e.target.value }))}
                              style={{
                                width: "100%", padding: "4px 8px", borderRadius: 6,
                                border: "1.5px solid var(--border-strong)", fontSize: "0.82rem",
                              }}
                            />
                          ) : (
                            <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                              {t.categoria || "—"}
                            </span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 6 }}>
                            {isEditing ? (
                              <>
                                <button
                                  type="button"
                                  className="table-button"
                                  disabled={twSaving}
                                  onClick={() => saveTypeWeight(twEditing)}
                                  style={{ fontSize: "0.75rem", padding: "4px 10px" }}
                                >
                                  Salvar
                                </button>
                                <button
                                  type="button"
                                  className="ghost-button"
                                  onClick={() => setTwEditing(null)}
                                  style={{ fontSize: "0.75rem" }}
                                >
                                  ✕
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  className="table-button"
                                  onClick={() => setTwEditing({ ...t })}
                                  style={{ fontSize: "0.75rem", padding: "4px 10px" }}
                                >
                                  Editar
                                </button>
                                {t.configurado && t.id && (
                                  <button
                                    type="button"
                                    className="ghost-button"
                                    onClick={() => removeTypeWeight(t.id, t.tipo)}
                                    style={{ fontSize: "0.75rem", color: "#bf3535" }}
                                  >
                                    ✕
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
