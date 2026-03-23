import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";


export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form);
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen-center auth-screen">
      <div className="auth-card">
        <div className="auth-copy">
          <p className="eyebrow">SEI BI</p>
          <h1>Business Intelligence para processos administrativos</h1>
          <span>
            Faça login, envie os relatórios CSV do SEI e acompanhe produtividade, permanência e alertas críticos.
          </span>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
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

          {error ? <div className="alert error">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>

          <div className="login-hint">Use o email e a senha cadastrados pelo administrador.</div>
        </form>
      </div>
    </div>
  );
}
