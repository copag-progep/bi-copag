import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
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
  "sei_usuario.excluido":{ label: "DE-PARA excluído",        color: "var(--danger)" },
  "sei_usuario.importado":{ label: "DE-PARA importado",      color: "var(--primary)" },
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
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Administração</p>
          <h1>Gestão de acessos e histórico</h1>
          <span>Crie novos logins com senha criptografada e acompanhe os uploads mais recentes.</span>
        </div>
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
    </div>
  );
}
