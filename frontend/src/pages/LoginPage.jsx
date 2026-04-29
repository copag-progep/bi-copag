import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";


export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">

        <div className="auth-copy">
          <div>
            <div className="auth-badge">
              <span className="badge-title">SEI BI</span>
              <span className="badge-divider" />
              <span className="badge-sub">COPAG · UFC</span>
            </div>
            <h1>Business Intelligence para o SEI</h1>
            <p className="auth-desc">
              Dashboards, indicadores de produtividade e alertas de processos
              parados — tudo a partir dos relatórios CSV do SEI.
            </p>
          </div>
          <div className="auth-stats">
            <div className="auth-stat-item">
              <strong>5</strong>
              <span>Dashboards analíticos</span>
            </div>
            <div className="auth-stat-item">
              <strong>6</strong>
              <span>Setores monitorados</span>
            </div>
            <div className="auth-stat-item">
              <strong>SEI</strong>
              <span>Integrado via CSV</span>
            </div>
          </div>
        </div>

        <div className="auth-form-panel">
          <div>
            <h2>Entrar na plataforma</h2>
            <p className="auth-hint">
              Use o email e a senha cadastrados pelo administrador.
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                placeholder="seu.email@ufc.br"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                required
                autoComplete="email"
              />
            </label>

            <label className="field">
              <span>Senha</span>
              <input
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                required
                autoComplete="current-password"
              />
            </label>

            {error ? <div className="alert error">{error}</div> : null}

            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? "Entrando..." : "Entrar →"}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
