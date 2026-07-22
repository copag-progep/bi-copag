import * as XLSX from "xlsx";

function fmtDate(val) {
  if (!val) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
      new Date(`${val}T00:00:00Z`)
    );
  } catch {
    return val;
  }
}

export function generateAttributionsExcel({ items, stats, dataReferencia, filtersText }) {
  const wb = XLSX.utils.book_new();

  /* ── Linha de informações ──────────────────────── */
  const infoRows = [
    ["AnalyticSEI — Relatório de Atribuições por Processo"],
    [`Data de referência: ${fmtDate(dataReferencia)}`],
    ...(filtersText ? [[`Filtros: ${filtersText}`]] : []),
    [],
    [
      `Total: ${stats.total}`,
      `Com atribuição: ${stats.totalCom}`,
      `Sem atribuição: ${stats.totalSem}`,
      `Maior tempo: ${stats.maxDias}d`,
    ],
    [],
    /* Cabeçalho da tabela */
    ["Atribuição", "Protocolo", "Tipo", "Setor", "Entrada no setor", "Dias no setor", "Atribuído desde", "Dias na atribuição", "Múltiplos setores"],
  ];

  /* ── Linhas de dados ───────────────────────────── */
  const dataRows = items.map((item) => [
    item.atribuicao || "Sem atribuição",
    item.protocolo || "",
    item.tipo || "—",
    item.setor || "",
    fmtDate(item.entrada_setor),
    item.dias_no_setor,
    fmtDate(item.entrada_atribuicao),
    item.dias_com_atribuicao,
    item.multiplos_setores ? "Sim" : "Não",
  ]);

  const ws = XLSX.utils.aoa_to_sheet([...infoRows, ...dataRows]);

  /* ── Largura das colunas ───────────────────────── */
  ws["!cols"] = [
    { wch: 32 }, // Atribuição
    { wch: 26 }, // Protocolo
    { wch: 44 }, // Tipo
    { wch: 18 }, // Setor
    { wch: 17 }, // Entrada no setor
    { wch: 14 }, // Dias no setor
    { wch: 17 }, // Atribuído desde
    { wch: 17 }, // Dias na atribuição
    { wch: 17 }, // Múltiplos setores
  ];

  XLSX.utils.book_append_sheet(wb, ws, "Atribuições");

  const safe = (dataReferencia || "relatorio").replace(/-/g, "");
  XLSX.writeFile(wb, `atribuicoes_${safe}.xlsx`);
}
