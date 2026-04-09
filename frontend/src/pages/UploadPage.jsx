import { useEffect, useState } from "react";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import { useAuth } from "../context/AuthContext";
import { useFilters } from "../context/FiltersContext";


const setores = ["DIAPE", "DICAT", "DIJOR", "DICAF", "DICAF-CHEFIA", "DICAF-REPOSICOES"];
const PAGE_SIZE = 30;


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

function normalizeUploadsPayload(payload, page) {
  if (Array.isArray(payload)) {
    const total = payload.length;
    const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
    const start = (page - 1) * PAGE_SIZE;
    return {
      items: payload.slice(start, start + PAGE_SIZE),
      total,
      totalPages,
    };
  }

  return {
    items: payload?.items || [],
    total: payload?.total || 0,
    totalPages: payload?.total_pages || 1,
  };
}


export default function UploadPage() {
  const { user } = useAuth();
  const { reloadOptions } = useFilters();
  const [form, setForm] = useState({
    setor: "DIAPE",
    data_relatorio: new Date().toISOString().slice(0, 10),
    file: null,
  });
  const [uploads, setUploads] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUploads, setTotalUploads] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [editingUploadId, setEditingUploadId] = useState(null);
  const [editingDate, setEditingDate] = useState("");
  const [savingUploadId, setSavingUploadId] = useState(null);
  const [deletingUploadId, setDeletingUploadId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadUploads(page = currentPage) {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/uploads", {
        params: {
          page,
          page_size: PAGE_SIZE,
        },
      });
      const normalized = normalizeUploadsPayload(data, page);
      setUploads(normalized.items);
      setTotalUploads(normalized.total);
      setTotalPages(normalized.totalPages);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar uploads.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUploads(currentPage);
  }, [currentPage]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

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
      if (currentPage === 1) {
        await loadUploads(1);
      } else {
        setCurrentPage(1);
      }
      await reloadOptions({ focusLatestDate: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha no envio do relatorio.");
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
      setError("Informe a nova data do relatorio.");
      return;
    }

    setSavingUploadId(upload.id);
    setMessage("");
    setError("");

    try {
      await api.patch(`/uploads/${upload.id}`, {
        data_relatorio: editingDate,
      });
      setMessage(`Data do relatorio de ${upload.original_filename} atualizada com sucesso.`);
      cancelEditing();
      await loadUploads(currentPage);
      await reloadOptions({ focusLatestDate: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao atualizar a data do relatorio.");
    } finally {
      setSavingUploadId(null);
    }
  }

  async function handleDelete(upload) {
    const confirmed = window.confirm(
      `Deseja excluir o relatorio ${upload.original_filename}? Esta acao removera tambem os processos desse snapshot.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingUploadId(upload.id);
    setMessage("");
    setError("");

    try {
      const { data } = await api.delete(`/uploads/${upload.id}`);
      setMessage(data.message || "Relatorio excluido com sucesso.");
      if (editingUploadId === upload.id) {
        cancelEditing();
      }
      await loadUploads(currentPage);
      await reloadOptions({ focusLatestDate: true });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao excluir o relatorio.");
    } finally {
      setDeletingUploadId(null);
    }
  }

  const uploadColumns = [
    { key: "setor", label: "Setor" },
    {
      key: "data_relatorio",
      label: "Data do relatorio",
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
    ...(user?.is_admin
      ? [
          {
            key: "actions",
            label: "Acoes",
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
        ]
      : []),
  ];

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Envio diario</p>
          <h1>Enviar Relatorio SEI</h1>
          <span>Associe o arquivo CSV ao setor e a data do snapshot para atualizar os dashboards automaticamente.</span>
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
            <span>Data do relatorio</span>
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
            <h3>Historico recente de uploads</h3>
            <p>
              {user?.is_admin
                ? "Voce pode corrigir a data de um snapshot ou remover um relatorio ja enviado."
                : "Os snapshots enviados aqui alimentam automaticamente os dashboards."}
            </p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando uploads..." />
        ) : (
          <>
            <DataTable columns={uploadColumns} rows={uploads} emptyMessage="Nenhum relatorio enviado ate o momento." />
            <div className="pagination-bar">
              <span className="pagination-summary">
                Pagina {currentPage} de {totalPages} | {totalUploads} relatorios
              </span>
              <div className="table-actions">
                <button
                  type="button"
                  className="table-button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="table-button"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                >
                  Proxima
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
