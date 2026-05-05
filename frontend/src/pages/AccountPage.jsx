import { useState } from "react";

import api from "../api/client";
import { useAuth } from "../context/AuthContext";


export default function AccountPage() {
  const { user } = useAuth();
  const [form, setForm] = useState({ senha_atual: "", nova_senha: "", confirmar_senha: "" });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    if (form.nova_senha !== form.confirmar_senha) {
      setError("A nova senha e a confirmação não coincidem.");
      return;
    }
    if (form.nova_senha === form.senha_atual) {
      setError("A nova senha deve ser diferente da senha atual.");
      return;
    }

    setLoading(true);
    try {
      await api.patch("/auth/password", {
        senha_atual: form.senha_atual,
        nova_senha: form.nova_senha,
      });
      setMessage("Senha alterada com sucesso.");
      setForm({ senha_atual: "", nova_senha: "", confirmar_senha: "" });
    } catch (err) {
      setError(err.response?.data?.detail || "Não foi possível alterar a senha.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Conta</p>
          <h1>Minha conta</h1>
          <span>Gerencie suas informações e altere sua senha de acesso.</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Informações do usuário</h3>
          </div>
        </div>
        <div style={{ display: "grid", gap: 14, marginTop: 12 }}>
          {[
            { label: "Nome",   value: user?.name },
            { label: "E-mail", value: user?.email },
            { label: "Perfil", value: user?.is_admin ? "Administrador" : "Servidor" },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", gap: 16, alignItems: "center" }}>
              <span style={{ color: "var(--muted)", fontWeight: 700, fontSize: "0.78rem",
                textTransform: "uppercase", letterSpacing: "0.07em", minWidth: 70 }}>
                {label}
              </span>
              <span style={{ color: "var(--ink)", fontWeight: 500 }}>{value}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Alterar senha</h3>
            <p>Informe sua senha atual para definir uma nova. Mínimo de 6 caracteres.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit} style={{ marginTop: 8 }}>
          <label className="field">
            <span>Senha atual</span>
            <input
              type="password"
              value={form.senha_atual}
              onChange={(e) => setForm((f) => ({ ...f, senha_atual: e.target.value }))}
              autoComplete="current-password"
              required
            />
          </label>

          <label className="field">
            <span>Nova senha</span>
            <input
              type="password"
              value={form.nova_senha}
              onChange={(e) => setForm((f) => ({ ...f, nova_senha: e.target.value }))}
              autoComplete="new-password"
              placeholder="Mínimo 6 caracteres"
              required
            />
          </label>

          <label className="field">
            <span>Confirmar nova senha</span>
            <input
              type="password"
              value={form.confirmar_senha}
              onChange={(e) => setForm((f) => ({ ...f, confirmar_senha: e.target.value }))}
              autoComplete="new-password"
              required
            />
          </label>

          {message ? <div className="alert success full-width">{message}</div> : null}
          {error   ? <div className="alert error   full-width">{error}</div>   : null}

          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "Alterando..." : "Alterar senha"}
          </button>
        </form>
      </section>
    </div>
  );
}
