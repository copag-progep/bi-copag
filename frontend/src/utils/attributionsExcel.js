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

function flagLabel(days) {
  if (days >= 90) return "90d+";
  if (days >= 60) return "60–89d";
  if (days >= 45) return "45–59d";
  if (days >= 30) return "30–44d";
  if (days >= 15) return "15–29d";
  return "<15d";
}

export function generateAttributionsExcel({ items, stats, dataReferencia, filtersText }) {
  const wb = XLSX.utils.book_new();

  /* ── Linha de informações ──────────────────────── */
  const infoRows = [
    ["SEI BI COPAG — Relatório de Atribuições por Processo"],
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
    ["Atribuição", "Protocolo", "Tipo", "Setor", "Desde", "Dias", "Faixa", "Múltiplos setores"],
  ];

  /* ── Linhas de dados ───────────────────────────── */
  const dataRows = items.map((item) => [
    item.atribuicao || "Sem atribuição",
    item.protocolo || "",
    item.tipo || "—",
    item.setor || "",
    fmtDate(item.entrada_atribuicao),
    item.dias_com_atribuicao,
    flagLabel(item.dias_com_atribuicao),
    item.multiplos_setores ? "Sim" : "Não",
  ]);

  const ws = XLSX.utils.aoa_to_sheet([...infoRows, ...dataRows]);

  /* ── Largura das colunas ───────────────────────── */
  ws["!cols"] = [
    { wch: 32 }, // Atribuição
    { wch: 26 }, // Protocolo
    { wch: 44 }, // Tipo
    { wch: 18 }, // Setor
    { wch: 13 }, // Desde
    { wch: 8  }, // Dias
    { wch: 10 }, // Faixa
    { wch: 17 }, // Múltiplos setores
  ];

  XLSX.utils.book_append_sheet(wb, ws, "Atribuições");

  const safe = (dataReferencia || "relatorio").replace(/-/g, "");
  XLSX.writeFile(wb, `atribuicoes_${safe}.xlsx`);
}
