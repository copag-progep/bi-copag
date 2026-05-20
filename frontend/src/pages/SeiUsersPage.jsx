import { useEffect, useState } from "react";
import * as XLSX from "xlsx";

import api from "../api/client";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import { useAuth } from "../context/AuthContext";


const HEADER_ALIASES = {
  nome: "nome",
  nome_sei: "nome_sei",
  "nome sei": "nome_sei",
  usuario_sei: "usuario_sei",
  "usuario sei": "usuario_sei",
  "usuário_sei": "usuario_sei",
  "usuário sei": "usuario_sei",
};


function cleanValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}


function normalizeHeader(value) {
  return cleanValue(value)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}


async function extractImportRows(file) {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];

  if (!firstSheetName) {
    throw new Error("A planilha enviada não possui abas disponíveis.");
  }

  const worksheet = workbook.Sheets[firstSheetName];
  const rawRows = XLSX.utils.sheet_to_json(worksheet, { defval: "" });

  if (!rawRows.length) {
    throw new Error("A planilha enviada está vazia.");
  }

  const rows = rawRows
    .map((row) => {
      const mapped = {};
      Object.entries(row).forEach(([key, value]) => {
        const normalizedKey = normalizeHeader(key);
        const targetKey = HEADER_ALIASES[normalizedKey];
        if (targetKey) {
          mapped[targetKey] = cleanValue(value);
        }
      });
      return {
        nome: cleanValue(mapped.nome),
        nome_sei: cleanValue(mapped.nome_sei),
        usuario_sei: cleanValue(mapped.usuario_sei),
      };
    })
    .filter((row) => row.nome);

  if (!rows.length) {
    throw new Error("A planilha precisa conter a coluna NOME com ao menos uma linha preenchida.");
  }

  return rows;
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
    timeStyle: "short",
  }).format(parsed);
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}


export default function SeiUsersPage() {
  const { user } = useAuth();
  const [seiUsers, setSeiUsers] = useState([]);
  const [attributionCandidates, setAttributionCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [aliasSaving, setAliasSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [deletingAliasId, setDeletingAliasId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [form, setForm] = useState({
    nome: "",
    nome_sei: "",
    usuario_sei: "",
  });
  const [aliasForm, setAliasForm] = useState({
    targetId: "",
    alias: "",
  });

  if (!user?.is_admin) {
    return <div className="alert error">Acesso restrito a administradores.</div>;
  }

  async function loadSeiUsers() {
    setLoading(true);
    setError("");
    try {
      const [usersResponse, candidatesResponse] = await Promise.all([
        api.get("/admin/sei-users"),
        api.get("/admin/sei-users/attribution-candidates"),
      ]);
      setSeiUsers(usersResponse.data);
      setAttributionCandidates(candidatesResponse.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar a base de usuários SEI.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSeiUsers();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");

    try {
      await api.post("/admin/sei-users", form);
      setMessage("Usuário SEI salvo com sucesso. As atribuições já foram consolidadas nos dashboards.");
      setForm({ nome: "", nome_sei: "", usuario_sei: "" });
      await loadSeiUsers();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível salvar o usuário SEI.");
    } finally {
      setSaving(false);
    }
  }

  async function handleImport(event) {
    event.preventDefault();
    if (!importFile) {
      setError("Selecione a planilha de usuários SEI para importar.");
      return;
    }

    setImporting(true);
    setMessage("");
    setError("");

    try {
      const rows = await extractImportRows(importFile);
      const { data } = await api.post("/admin/sei-users/import-rows", {
        rows,
      });
      setMessage(
        `Importação concluída: ${data.imported} novos registros, ${data.updated} atualizados, ${data.total} linhas processadas.`
      );
      setImportFile(null);
      document.getElementById("sei-users-import-input").value = "";
      await loadSeiUsers();
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail || requestError.message || "Não foi possível importar a planilha de usuários SEI."
      );
    } finally {
      setImporting(false);
    }
  }

  async function handleDelete(row) {
    const confirmed = window.confirm(
      `Deseja excluir o vínculo de ${row.nome}? Os processos passarão a exibir a atribuição original do SEI quando não houver outro DE-PARA correspondente.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingId(row.id);
    setMessage("");
    setError("");

    try {
      const { data } = await api.delete(`/admin/sei-users/${row.id}`);
      setMessage(data.message || "Usuário SEI excluído com sucesso.");
      await loadSeiUsers();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível excluir o usuário SEI.");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleAliasSubmit(event) {
    event.preventDefault();
    if (!aliasForm.targetId || !aliasForm.alias.trim()) {
      setError("Escolha o usuário principal e informe o nome histórico que deve ser unido.");
      return;
    }

    setAliasSaving(true);
    setMessage("");
    setError("");

    try {
      const { data } = await api.post(`/admin/sei-users/${aliasForm.targetId}/aliases`, {
        alias: aliasForm.alias,
        merge_existing: true,
      });
      setMessage(data.message || "Histórico unido com sucesso.");
      setAliasForm({ targetId: aliasForm.targetId, alias: "" });
      await loadSeiUsers();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível unir os históricos de atribuição.");
    } finally {
      setAliasSaving(false);
    }
  }

  async function handleDeleteAlias(alias) {
    const confirmed = window.confirm(
      `Deseja remover o alias histórico ${alias.alias}? Os processos voltarão a seguir o DE-PARA disponível para esse nome.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingAliasId(alias.id);
    setMessage("");
    setError("");

    try {
      const { data } = await api.delete(`/admin/sei-users/aliases/${alias.id}`);
      setMessage(data.message || "Alias histórico removido com sucesso.");
      await loadSeiUsers();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Não foi possível remover o alias histórico.");
    } finally {
      setDeletingAliasId(null);
    }
  }

  const selectedCandidate = attributionCandidates.find(
    (candidate) => candidate.atribuicao === aliasForm.alias
  );

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Usuários SEI</p>
          <h1>Gestão do DE-PARA de atribuições</h1>
          <span>
            Relacione nome, nome exibido no SEI e usuário do servidor para consolidar a atribuição nos gráficos,
            filtros e rankings.
          </span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Novo vínculo manual</h3>
            <p>Cadastre aqui um novo servidor sempre que surgir um nome ou usuário ainda não mapeado.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>Nome canônico</span>
            <input
              type="text"
              value={form.nome}
              onChange={(event) => setForm((current) => ({ ...current, nome: event.target.value }))}
              placeholder="Ex.: Marilene Soares"
              required
            />
          </label>

          <label className="field">
            <span>Nome SEI</span>
            <input
              type="text"
              value={form.nome_sei}
              onChange={(event) => setForm((current) => ({ ...current, nome_sei: event.target.value }))}
              placeholder="Ex.: Marilene Feitosa"
            />
          </label>

          <label className="field">
            <span>Usuário SEI</span>
            <input
              type="text"
              value={form.usuario_sei}
              onChange={(event) => setForm((current) => ({ ...current, usuario_sei: event.target.value }))}
              placeholder="Ex.: marilene.feitosa"
            />
          </label>

          {message ? <div className="alert success full-width">{message}</div> : null}
          {error ? <div className="alert error full-width">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? "Salvando..." : "Salvar vínculo"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Unir históricos de atribuição</h3>
            <p>
              Use quando a mesma pessoa aparecer com nomes diferentes ao longo dos snapshots. O sistema preserva o nome
              bruto do SEI e passa a consolidar os indicadores no nome principal escolhido.
            </p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleAliasSubmit}>
          <label className="field">
            <span>Usuário principal</span>
            <select
              value={aliasForm.targetId}
              onChange={(event) => setAliasForm((current) => ({ ...current, targetId: event.target.value }))}
              required
            >
              <option value="">Selecione</option>
              {seiUsers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Nome histórico ou alternativo</span>
            <input
              type="text"
              list="sei-attribution-candidates"
              value={aliasForm.alias}
              onChange={(event) => setAliasForm((current) => ({ ...current, alias: event.target.value }))}
              placeholder="Ex.: ANA CRISTINA CAMINHA VIANA LOPES"
              required
            />
            <datalist id="sei-attribution-candidates">
              {attributionCandidates.map((candidate) => (
                <option key={candidate.atribuicao} value={candidate.atribuicao} />
              ))}
            </datalist>
          </label>

          <div className="alias-candidate-note">
            <span>Prévia do histórico</span>
            {selectedCandidate ? (
              <strong>
                {selectedCandidate.total_processos} registros entre {formatDate(selectedCandidate.primeira_data)} e{" "}
                {formatDate(selectedCandidate.ultima_data)}
              </strong>
            ) : (
              <strong>Digite ou escolha uma atribuição já encontrada nos relatórios.</strong>
            )}
          </div>

          <button type="submit" className="primary-button" disabled={aliasSaving}>
            {aliasSaving ? "Unindo..." : "Unir histórico"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Importar planilha de usuários SEI</h3>
            <p>
              Envie arquivos .xls, .xlsx ou .csv com as colunas NOME, NOME SEI e USUÁRIO SEI para atualizar a base em
              lote.
            </p>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleImport}>
          <label className="field full-width">
            <span>Planilha de correspondência</span>
            <input
              id="sei-users-import-input"
              type="file"
              accept=".xls,.xlsx,.csv"
              onChange={(event) => setImportFile(event.target.files?.[0] || null)}
              required
            />
          </label>

          <button type="submit" className="primary-button" disabled={importing || !importFile}>
            {importing ? "Importando..." : "Importar planilha"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Base atual de usuários SEI</h3>
            <p>Essa lista é usada para consolidar a coluna Atribuição em todas as análises do sistema.</p>
          </div>
        </div>
        {loading ? (
          <LoadingBlock label="Carregando usuários SEI..." />
        ) : (
          <DataTable
            columns={[
              { key: "nome", label: "Nome" },
              { key: "nome_sei", label: "Nome SEI" },
              { key: "usuario_sei", label: "Usuário SEI" },
              {
                key: "aliases",
                label: "Aliases históricos",
                render: (aliases = []) => {
                  if (!aliases.length) {
                    return <span className="table-helper">-</span>;
                  }
                  return (
                    <div className="alias-chip-list">
                      {aliases.map((alias) => (
                        <span key={alias.id} className="alias-chip">
                          {alias.alias}
                          <button
                            type="button"
                            onClick={() => handleDeleteAlias(alias)}
                            disabled={deletingAliasId === alias.id}
                            aria-label={`Remover alias ${alias.alias}`}
                          >
                            x
                          </button>
                        </span>
                      ))}
                    </div>
                  );
                },
              },
              { key: "created_at", label: "Criado em", render: (value) => formatDateTime(value) },
              {
                key: "actions",
                label: "Ações",
                render: (_, row) => (
                  <button
                    type="button"
                    className="table-button danger"
                    onClick={() => handleDelete(row)}
                    disabled={deletingId === row.id}
                  >
                    {deletingId === row.id ? "Excluindo..." : "Excluir"}
                  </button>
                ),
              },
            ]}
            rows={seiUsers}
            emptyMessage="Nenhum vínculo de usuário SEI cadastrado até o momento."
          />
        )}
      </section>
    </div>
  );
}
