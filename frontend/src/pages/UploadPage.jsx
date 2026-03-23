import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";


const setores = ["DIAPE", "DICAT", "DIJOR", "DICAF", "DICAF-CHEFIA", "DICAF-REPOSICOES"];


function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(parsed);
}


export default function UploadPage() {
  const [form, setForm] = useState({
    setor: "DIAPE",
    data_relatorio: new Date().toISOString().slice(0, 10),
    file: null,
  });
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [editingUploadId, setEditingUploadId] = useState(null);
  const [editingDate, setEditingDate] = useState("");
  const [savingUploadId, setSavingUploadId] = useState(null);
  const [deletingUploadId, setDeletingUploadId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadUploads() {
    setLoading(true);
    try {
      const { data } = await api.get("/uploads");
      setUploads(data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar uploads.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUploads();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setSending(true);
    setMessage("");
    setError("");

    try {
      const payload = new FormData();
      payload.append("setor", form.setor);
      payload.append("data_relatorio", form.data_relatorio);
      payload.append("file", form.file);

      const { data } = await api.post("/uploads", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMessage(`${data.message} ${data.total_registros} registros processados.`);
      setForm((current) => ({ ...current, file: null }));
      document.getElementById("upload-file-input").value = "";
      await loadUploads();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha no envio do relatório.");
    } finally {
      setSending(false);
    }
  }

  function startEditing(upload) {
    setEditingUploadId(upload.id);
    setEditingDate(upload.data_relatorio);
    setMessage("");
    setError("");
  }

  function cancelEditing() {
    setEditingUploadId(null);
    setEditingDate("");
  }

  async function handleSaveDate(upload) {
    if (!editingDate) {
      setError("Informe a nova data do relatório.");
      return;
    }

    setSavingUploadId(upload.id);
    setMessage("");
    setError("");

    try {
      await api.patch(`/uploads/${upload.id}`, {
        data_relatorio: editingDate,
      });
      setMessage(`Data do relatório de ${upload.original_filename} atualizada com sucesso.`);
      cancelEditing();
      await loadUploads();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao atualizar a data do relatório.");
    } finally {
      setSavingUploadId(null);
    }
  }

  async function handleDelete(upload) {
    const confirmed = window.confirm(
      `Deseja excluir o relatório ${upload.original_filename}? Esta ação removerá também os processos desse snapshot.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingUploadId(upload.id);
    setMessage("");
    setError("");

    try {
      const { data } = await api.delete(`/uploads/${upload.id}`);
      setMessage(data.message || "Relatório excluído com sucesso.");
      if (editingUploadId === upload.id) {
        cancelEditing();
      }
      await loadUploads();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao excluir o relatório.");
    } finally {
      setDeletingUploadId(null);
    }
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Envio diário</p>
          <h1>Enviar Relatório SEI</h1>
          <span>Associe o arquivo CSV ao setor e à data do snapshot para atualizar os dashboards automaticamente.</span>
        </div>
      </section>

      <section className="panel">
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>Setor</span>
            <select value={form.setor} onChange={(event) => setForm((current) => ({ ...current, setor: event.target.value }))}>
              {setores.map((setor) => (
                <option key={setor} value={setor}>
                  {setor}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Data do relatório</span>
            <input
              type="date"
              value={form.data_relatorio}
              onChange={(event) => setForm((current) => ({ ...current, data_relatorio: event.target.value }))}
              required
            />
          </label>

          <label className="field full-width">
            <span>Arquivo CSV exportado do SEI</span>
            <input
              id="upload-file-input"
              type="file"
              accept=".csv"
              onChange={(event) => setForm((current) => ({ ...current, file: event.target.files?.[0] || null }))}
              required
            />
          </label>

          {message ? <div className="alert success full-width">{message}</div> : null}
          {error ? <div className="alert error full-width">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={sending || !form.file}>
            {sending ? "Enviando..." : "Enviar"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Histórico recente de uploads</h3>
            <p>Você pode corrigir a data de um snapshot ou remover um relatório já enviado.</p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando uploads..." />
        ) : (
          <DataTable
            columns={[
              { key: "setor", label: "Setor" },
              {
                key: "data_relatorio",
                label: "Data do relatório",
                render: (value, row) =>
                  editingUploadId === row.id ? (
                    <div className="inline-date-editor">
                      <input
                        className="table-input"
                        type="date"
                        value={editingDate}
                        onChange={(event) => setEditingDate(event.target.value)}
                      />
                      <small className="table-helper">Corrija a data e salve.</small>
                    </div>
                  ) : (
                    formatDate(value)
                  ),
              },
              {
                key: "data_upload",
                label: "Importado em",
                render: (value) => formatDateTime(value),
              },
              { key: "original_filename", label: "Arquivo" },
              { key: "total_records", label: "Registros" },
              {
                key: "actions",
                label: "Ações",
                render: (_, row) =>
                  editingUploadId === row.id ? (
                    <div className="table-actions">
                      <button
                        type="button"
                        className="table-button primary"
                        onClick={() => handleSaveDate(row)}
                        disabled={savingUploadId === row.id || deletingUploadId === row.id}
                      >
                        {savingUploadId === row.id ? "Salvando..." : "Salvar"}
                      </button>
                      <button
                        type="button"
                        className="table-button"
                        onClick={cancelEditing}
                        disabled={savingUploadId === row.id}
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <div className="table-actions">
                      <button
                        type="button"
                        className="table-button"
                        onClick={() => startEditing(row)}
                        disabled={deletingUploadId === row.id}
                      >
                        Editar data
                      </button>
                      <button
                        type="button"
                        className="table-button danger"
                        onClick={() => handleDelete(row)}
                        disabled={deletingUploadId === row.id}
                      >
                        {deletingUploadId === row.id ? "Excluindo..." : "Excluir"}
                      </button>
                    </div>
                  ),
              },
            ]}
            rows={uploads}
          />
        )}
      </section>
    </div>
  );
}
