import { useEffect, useState } from "react";

import api from "../api/client";
import BarChartCard from "../charts/BarChartCard";
import LineChartCard from "../charts/LineChartCard";
import DataTable from "../components/DataTable";
import LoadingBlock from "../components/LoadingBlock";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/AuthContext";

const ENTRY_FIELDS = [
  { key: "processos_gerados", indicator: "Processos gerados no per\u00edodo", shortLabel: "Proc. gerados" },
  {
    key: "processos_tramitacao",
    indicator: "Processos com tramita\u00e7\u00e3o no per\u00edodo",
    shortLabel: "Proc. tramitacao",
  },
  {
    key: "processos_fechados",
    indicator: "Processos com andamento fechado na unidade ao final do per\u00edodo",
    shortLabel: "Proc. fechados",
  },
  {
    key: "processos_abertos",
    indicator: "Processos com andamento aberto na unidade ao final do per\u00edodo",
    shortLabel: "Proc. abertos",
  },
  { key: "documentos_gerados", indicator: "Documentos gerados no per\u00edodo", shortLabel: "Docs gerados" },
  { key: "documentos_externos", indicator: "Documentos externos no per\u00edodo", shortLabel: "Docs externos" },
];

const DEFAULT_SETORES = ["DIAPE", "DICAT", "DIJOR", "DICAF", "DICAF-CHEFIA", "DICAF-REPOSICOES"];

const MONTH_OPTIONS = [
  { value: 1, label: "Janeiro" },
  { value: 2, label: "Fevereiro" },
  { value: 3, label: "Mar\u00e7o" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Maio" },
  { value: 6, label: "Junho" },
  { value: 7, label: "Julho" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Setembro" },
  { value: 10, label: "Outubro" },
  { value: 11, label: "Novembro" },
  { value: 12, label: "Dezembro" },
];

const NUMBER_FORMATTER = new Intl.NumberFormat("pt-BR");
const PAGE_SIZE = 50;

function buildLatestReference(rows) {
  if (!rows.length) {
    return null;
  }

  return rows.reduce((latest, row) => {
    if (!latest) {
      return row;
    }

    if (row.ano > latest.ano) {
      return row;
    }

    if (row.ano === latest.ano && row.num_mes > latest.num_mes) {
      return row;
    }

    return latest;
  }, null);
}

function buildKpiData(rows) {
  return ENTRY_FIELDS.map((field) => ({
    ...field,
    value: rows
      .filter((row) => row.indicador === field.indicator)
      .reduce((total, row) => total + Number(row.valor || 0), 0),
  }));
}

function buildTrendData(rows, indicator, setor, ano, mes) {
  return rows
    .filter((row) => row.indicador === indicator)
    .filter((row) => (!setor ? true : row.setor === setor))
    .filter((row) => (!ano ? true : row.ano === Number(ano)))
    .filter((row) => (!mes ? true : row.num_mes === Number(mes)))
    .map((row) => ({
      mes_ano: row.mes_ano,
      valor: Number(row.valor || 0),
      setor: row.setor,
    }));
}

function buildManagementRows(rows) {
  return [...rows]
    .sort((left, right) => {
      if (left.ano !== right.ano) {
        return right.ano - left.ano;
      }

      if (left.num_mes !== right.num_mes) {
        return right.num_mes - left.num_mes;
      }

      if (left.setor !== right.setor) {
        return left.setor.localeCompare(right.setor);
      }

      return left.indicador.localeCompare(right.indicador);
    })
    .map((row) => ({
      id: row.id,
      periodo: row.mes_ano,
      setor: row.setor,
      indicador: row.indicador,
      valor_raw: Number(row.valor || 0),
      valor: NUMBER_FORMATTER.format(Number(row.valor || 0)),
      atualizado_em: new Date(row.updated_at).toLocaleString("pt-BR"),
    }));
}

function buildLatestTable(rows, selectedSetor) {
  const bucket = new Map();

  rows
    .filter((row) => (!selectedSetor ? true : row.setor === selectedSetor))
    .forEach((row) => {
      if (!bucket.has(row.setor)) {
        bucket.set(row.setor, {
          setor: row.setor,
          processos_gerados: 0,
          processos_tramitacao: 0,
          processos_fechados: 0,
          processos_abertos: 0,
          documentos_gerados: 0,
          documentos_externos: 0,
        });
      }

      const current = bucket.get(row.setor);
      const matchingField = ENTRY_FIELDS.find((field) => field.indicator === row.indicador);
      if (matchingField) {
        current[matchingField.key] = Number(row.valor || 0);
      }
    });

  return Array.from(bucket.values()).sort((left, right) => left.setor.localeCompare(right.setor));
}

function buildEntryInitialState(defaultSetor) {
  const now = new Date();
  return {
    setor: defaultSetor || DEFAULT_SETORES[0],
    ano: String(now.getFullYear()),
    num_mes: String(now.getMonth() + 1),
    processos_gerados: "0",
    processos_tramitacao: "0",
    processos_fechados: "0",
    processos_abertos: "0",
    documentos_gerados: "0",
    documentos_externos: "0",
  };
}

export default function MonthlyStatsPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ rows: [], setores: [], indicadores: [], anos: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [historyFile, setHistoryFile] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [editingRowId, setEditingRowId] = useState(null);
  const [editingValue, setEditingValue] = useState("");
  const [dashboardFilters, setDashboardFilters] = useState({
    setor: "",
    indicador: ENTRY_FIELDS[0].indicator,
    ano: "",
    mes: "",
  });
  const [entryForm, setEntryForm] = useState(buildEntryInitialState(DEFAULT_SETORES[0]));

  async function loadMonthlyStats() {
    setLoading(true);
    setError("");

    try {
      const response = await api.get("/monthly-stats");
      setData(response.data);
      setEntryForm((current) => ({
        ...current,
        setor: current.setor || response.data.setores?.[0] || DEFAULT_SETORES[0],
      }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Falha ao carregar os indicadores mensais.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMonthlyStats();
  }, []);

  const filteredRows = data.rows
    .filter((row) => (!dashboardFilters.setor ? true : row.setor === dashboardFilters.setor))
    .filter((row) => (!dashboardFilters.ano ? true : row.ano === Number(dashboardFilters.ano)))
    .filter((row) => (!dashboardFilters.mes ? true : row.num_mes === Number(dashboardFilters.mes)));

  const latestReference = buildLatestReference(filteredRows);
  const latestRows = latestReference
    ? filteredRows.filter((row) => row.ano === latestReference.ano && row.num_mes === latestReference.num_mes)
    : [];
  const kpiData = buildKpiData(latestRows);
  const trendData = buildTrendData(
    data.rows,
    dashboardFilters.indicador,
    dashboardFilters.setor,
    dashboardFilters.ano,
    dashboardFilters.mes
  );
  const latestTableRows = buildLatestTable(latestRows, dashboardFilters.setor);
  const focusedIndicatorRows = data.rows
    .filter((row) => row.indicador === dashboardFilters.indicador)
    .filter((row) => (!dashboardFilters.setor ? true : row.setor === dashboardFilters.setor))
    .filter((row) => (!dashboardFilters.ano ? true : row.ano === Number(dashboardFilters.ano)))
    .filter((row) => (!dashboardFilters.mes ? true : row.num_mes === Number(dashboardFilters.mes)));
  const focusedIndicatorAverage = focusedIndicatorRows.length
    ? Math.round(
        focusedIndicatorRows.reduce((total, row) => total + Number(row.valor || 0), 0) / focusedIndicatorRows.length
      )
    : 0;
  const managementRows = buildManagementRows(data.rows);
  const availableSetores = data.setores.length ? data.setores : DEFAULT_SETORES;
  const totalPages = Math.max(1, Math.ceil(managementRows.length / PAGE_SIZE));
  const paginatedManagementRows = managementRows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  async function handleImportHistory(event) {
    event.preventDefault();
    if (!historyFile) {
      setError("Selecione o CSV mensal para importar.");
      return;
    }

    setImporting(true);
    setMessage("");
    setError("");

    try {
      const payload = new FormData();
      payload.append("file", historyFile);
      const response = await api.post("/admin/monthly-stats/import", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setMessage(
        `Importacao mensal concluida: ${response.data.imported} novos registros, ${response.data.updated} atualizados e ${response.data.total} linhas processadas.`
      );
      setHistoryFile(null);
      const input = document.getElementById("monthly-stats-file-input");
      if (input) {
        input.value = "";
      }
      setCurrentPage(1);
      await loadMonthlyStats();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Nao foi possivel importar o historico mensal do SEI.");
    } finally {
      setImporting(false);
    }
  }

  async function handleSaveEntry(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");

    try {
      const payload = {
        setor: entryForm.setor,
        ano: Number(entryForm.ano),
        num_mes: Number(entryForm.num_mes),
      };

      ENTRY_FIELDS.forEach((field) => {
        payload[field.key] = Number(entryForm[field.key] || 0);
      });

      const response = await api.post("/admin/monthly-stats/month-entry", payload);
      setMessage(
        `Lancamento mensal salvo com sucesso: ${response.data.imported} registros criados e ${response.data.updated} atualizados.`
      );
      setCurrentPage(1);
      await loadMonthlyStats();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Nao foi possivel salvar os indicadores mensais.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRowEdit(rowId) {
    setSaving(true);
    setMessage("");
    setError("");

    try {
      await api.patch(`/admin/monthly-stats/${rowId}`, { valor: Number(editingValue || 0) });
      setMessage("Indicador mensal atualizado com sucesso.");
      setEditingRowId(null);
      setEditingValue("");
      await loadMonthlyStats();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Nao foi possivel atualizar o indicador mensal.");
    } finally {
      setSaving(false);
    }
  }

  function startEditingRow(row) {
    setEditingRowId(row.id);
    setEditingValue(String(row.valor_raw));
    setMessage("");
    setError("");
  }

  function cancelEditingRow() {
    setEditingRowId(null);
    setEditingValue("");
  }

  if (loading) {
    return <LoadingBlock label="Montando indicadores mensais do SEI..." />;
  }

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Indicadores mensais</p>
          <h1>Painel historico do desempenho do SEI</h1>
          <span>
            Acompanhe os seis indicadores mensais por divisao e mantenha a serie historica atualizada a partir de
            2025.
          </span>
        </div>
      </section>

      {user?.is_admin ? (
        <section className="panel">
          <div className="tab-strip">
            <button
              type="button"
              className={`tab-button ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => setActiveTab("dashboard")}
            >
              Dashboard mensal
            </button>
            <button
              type="button"
              className={`tab-button ${activeTab === "gestao" ? "active" : ""}`}
              onClick={() => setActiveTab("gestao")}
            >
              Atualizacao mensal
            </button>
          </div>
        </section>
      ) : null}

      {message ? <div className="alert success">{message}</div> : null}
      {error ? <div className="alert error">{error}</div> : null}

      {activeTab === "dashboard" ? (
        <>
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Filtros do painel mensal</h3>
                <p>Defina o setor, o indicador em foco e o ano para analisar a evolucao historica.</p>
              </div>
            </div>
            <div className="form-grid monthly-filter-grid">
              <label className="field">
                <span>Setor</span>
                <select
                  value={dashboardFilters.setor}
                  onChange={(event) =>
                    setDashboardFilters((current) => ({ ...current, setor: event.target.value }))
                  }
                >
                  <option value="">Todos</option>
                  {availableSetores.map((setor) => (
                    <option key={setor} value={setor}>
                      {setor}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Indicador em foco</span>
                <select
                  value={dashboardFilters.indicador}
                  onChange={(event) =>
                    setDashboardFilters((current) => ({ ...current, indicador: event.target.value }))
                  }
                >
                  {ENTRY_FIELDS.map((field) => (
                    <option key={field.indicator} value={field.indicator}>
                      {field.indicator}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Ano</span>
                <select
                  value={dashboardFilters.ano}
                  onChange={(event) => setDashboardFilters((current) => ({ ...current, ano: event.target.value }))}
                >
                  <option value="">Todos</option>
                  {data.anos.map((ano) => (
                    <option key={ano} value={ano}>
                      {ano}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Mes</span>
                <select
                  value={dashboardFilters.mes}
                  onChange={(event) => setDashboardFilters((current) => ({ ...current, mes: event.target.value }))}
                >
                  <option value="">Todos</option>
                  {MONTH_OPTIONS.map((month) => (
                    <option key={month.value} value={month.value}>
                      {month.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>

          <section className="stats-grid">
            {kpiData.map((field) => (
              <StatCard
                key={field.key}
                label={field.shortLabel}
                value={field.value}
                hint={latestReference ? `${latestReference.mes} de ${latestReference.ano}` : "Sem dados"}
              />
            ))}
            <StatCard
              label="Media historica"
              value={NUMBER_FORMATTER.format(focusedIndicatorAverage)}
              hint={dashboardFilters.indicador}
            />
            <StatCard
              label="Setor selecionado"
              value={dashboardFilters.setor || "Todos os setores"}
              hint={dashboardFilters.mes ? MONTH_OPTIONS.find((month) => month.value === Number(dashboardFilters.mes))?.label : "Todos os meses"}
            />
          </section>

          <section className="charts-grid">
            <LineChartCard
              title="Evolucao mensal do indicador em foco"
              subtitle={
                dashboardFilters.setor
                  ? `Serie mensal de ${dashboardFilters.indicador} para ${dashboardFilters.setor}.`
                  : `Serie mensal de ${dashboardFilters.indicador} para todas as divisoes.`
              }
              data={trendData}
              xKey="mes_ano"
              valueKey="valor"
              seriesKey={dashboardFilters.setor ? undefined : "setor"}
            />
            <BarChartCard
              title="Indicadores no ultimo mes disponivel"
              subtitle={
                latestReference
                  ? `Consolidado de ${latestReference.mes_ano} ${dashboardFilters.setor ? `em ${dashboardFilters.setor}` : "em todas as divisoes"}.`
                  : "Nenhum dado mensal disponivel."
              }
              data={kpiData.map((field) => ({ label: field.shortLabel, value: field.value }))}
              color="#0f5f73"
            />
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Resumo do ultimo mes</h3>
                <p>
                  Valores consolidados por divisao para{" "}
                  {latestReference ? latestReference.mes_ano : "o periodo mais recente"}.
                </p>
              </div>
            </div>
            <DataTable
              columns={[
                { key: "setor", label: "Setor" },
                { key: "processos_gerados", label: "Proc. gerados" },
                { key: "processos_tramitacao", label: "Proc. tramitacao" },
                { key: "processos_fechados", label: "Proc. fechados" },
                { key: "processos_abertos", label: "Proc. abertos" },
                { key: "documentos_gerados", label: "Docs gerados" },
                { key: "documentos_externos", label: "Docs externos" },
              ]}
              rows={latestTableRows}
              emptyMessage="Nenhum indicador mensal carregado ate o momento."
            />
          </section>
        </>
      ) : (
        <div className="page-grid">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Importar historico mensal do SEI</h3>
                <p>Envie o CSV historico com os indicadores mensais das divisoes para popular os graficos.</p>
              </div>
            </div>
            <form className="form-grid" onSubmit={handleImportHistory}>
              <label className="field full-width">
                <span>Arquivo CSV historico</span>
                <input
                  id="monthly-stats-file-input"
                  type="file"
                  accept=".csv"
                  onChange={(event) => setHistoryFile(event.target.files?.[0] || null)}
                  required
                />
              </label>

              <button type="submit" className="primary-button" disabled={importing || !historyFile}>
                {importing ? "Importando..." : "Importar historico"}
              </button>
            </form>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Atualizacao mensal a partir de 2025</h3>
                <p>Informe os seis indicadores da divisao e do mes para atualizar a serie historica continuamente.</p>
              </div>
            </div>
            <form className="form-grid" onSubmit={handleSaveEntry}>
              <label className="field">
                <span>Setor</span>
                <select
                  value={entryForm.setor}
                  onChange={(event) => setEntryForm((current) => ({ ...current, setor: event.target.value }))}
                >
                  {availableSetores.map((setor) => (
                    <option key={setor} value={setor}>
                      {setor}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Ano</span>
                <input
                  type="number"
                  min="2023"
                  max="2100"
                  value={entryForm.ano}
                  onChange={(event) => setEntryForm((current) => ({ ...current, ano: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>Mes</span>
                <select
                  value={entryForm.num_mes}
                  onChange={(event) => setEntryForm((current) => ({ ...current, num_mes: event.target.value }))}
                >
                  {MONTH_OPTIONS.map((month) => (
                    <option key={month.value} value={month.value}>
                      {month.label}
                    </option>
                  ))}
                </select>
              </label>

              {ENTRY_FIELDS.map((field) => (
                <label key={field.key} className="field">
                  <span>{field.indicator}</span>
                  <input
                    type="number"
                    min="0"
                    value={entryForm[field.key]}
                    onChange={(event) =>
                      setEntryForm((current) => ({ ...current, [field.key]: event.target.value }))
                    }
                    required
                  />
                </label>
              ))}

              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "Salvando..." : "Salvar mes"}
              </button>
            </form>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>Historico completo dos indicadores mensais</h3>
                <p>Lista consolidada dos dados importados e dos lancamentos feitos manualmente para conferencia em tela.</p>
              </div>
            </div>
            <DataTable
              columns={[
                { key: "periodo", label: "Periodo" },
                { key: "setor", label: "Setor" },
                { key: "indicador", label: "Indicador" },
                { key: "valor", label: "Valor" },
                { key: "atualizado_em", label: "Atualizado em" },
                {
                  key: "acoes",
                  label: "Acoes",
                  render: (_, row) =>
                    editingRowId === row.id ? (
                      <div className="table-actions">
                        <input
                          className="table-input"
                          type="number"
                          min="0"
                          value={editingValue}
                          onChange={(event) => setEditingValue(event.target.value)}
                        />
                        <button
                          type="button"
                          className="table-button primary"
                          disabled={saving}
                          onClick={() => handleSaveRowEdit(row.id)}
                        >
                          Salvar
                        </button>
                        <button type="button" className="table-button" onClick={cancelEditingRow}>
                          Cancelar
                        </button>
                      </div>
                    ) : (
                      <button type="button" className="table-button" onClick={() => startEditingRow(row)}>
                        Editar
                      </button>
                    ),
                },
              ]}
              rows={paginatedManagementRows}
              emptyMessage="Nenhum dado mensal cadastrado ate o momento."
            />
            <div className="pagination-bar">
              <span className="pagination-summary">
                Pagina {currentPage} de {totalPages} | {managementRows.length} registros
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
          </section>
        </div>
      )}
    </div>
  );
}
