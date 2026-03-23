import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import { useAuth } from "../context/AuthContext";


export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
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
      const [usersResponse, uploadsResponse] = await Promise.all([api.get("/admin/users"), api.get("/uploads")]);
      setUsers(usersResponse.data);
      setUploads(uploadsResponse.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar dados administrativos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAdminData();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.post("/admin/users", form);
      setMessage("Usuario criado com sucesso.");
      setForm({ name: "", email: "", password: "", is_admin: false });
      await loadAdminData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Nao foi possivel criar o usuario.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteUser(targetUser) {
    const confirmed = window.confirm(`Deseja excluir o usuario ${targetUser.name}?`);
    if (!confirmed) {
      return;
    }

    setDeletingUserId(targetUser.id);
    setMessage("");
    setError("");
    try {
      const { data } = await api.delete(`/admin/users/${targetUser.id}`);
      setMessage(data.message || "Usuario excluido com sucesso.");
      await loadAdminData();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Nao foi possivel excluir o usuario.");
    } finally {
      setDeletingUserId(null);
    }
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Administracao</p>
          <h1>Gestao de acessos e historico</h1>
          <span>Crie novos logins com senha criptografada e acompanhe os uploads mais recentes.</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Novo usuario</h3>
            <p>Cadastre contas e defina se o novo acesso tera privilegios administrativos.</p>
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
            {saving ? "Salvando..." : "Criar usuario"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Usuarios cadastrados</h3>
            <p>Contas disponiveis para autenticacao na aplicacao.</p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando usuarios..." />
        ) : (
          <DataTable
            columns={[
              { key: "name", label: "Nome" },
              { key: "email", label: "Email" },
              {
                key: "is_admin",
                label: "Perfil",
                render: (value) => (value ? "Administrador" : "Usuario"),
              },
              { key: "created_at", label: "Criado em" },
              ...(user?.is_admin
                ? [
                    {
                      key: "actions",
                      label: "Acoes",
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
            <h3>Ultimos uploads</h3>
            <p>Referencia rapida para auditoria do carregamento de snapshots.</p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando historico..." />
        ) : (
          <DataTable
            columns={[
              { key: "setor", label: "Setor" },
              { key: "data_relatorio", label: "Data do relatorio" },
              { key: "original_filename", label: "Arquivo" },
              { key: "total_records", label: "Registros" },
            ]}
            rows={uploads}
          />
        )}
      </section>
    </div>
  );
}
