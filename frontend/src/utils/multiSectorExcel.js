import * as XLSX from "xlsx";

function fmtDate(val) {
  if (!val) return "-";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
      new Date(`${val}T00:00:00Z`)
    );
  } catch {
    return val;
  }
}

export function generateMultiSectorExcel({ items, stats, dataReferencia, filtersText }) {
  const wb = XLSX.utils.book_new();

  const infoRows = [
    ["AnalyticSEI - Relatorio de Processos em Multiplos Setores"],
    [`Data de referencia: ${fmtDate(dataReferencia)}`],
    ...(filtersText ? [[`Filtros: ${filtersText}`]] : []),
    [],
    [
      `Total: ${stats.total}`,
      `Em 2 setores: ${stats.em2}`,
      `Em 3 ou mais setores: ${stats.em3mais}`,
      `Setores envolvidos: ${stats.setoresUnicos}`,
    ],
    [],
    ["Protocolo", "Setores", "Quantidade de setores", "Data do relatorio"],
  ];

  const dataRows = items.map((item) => [
    item.protocolo || "",
    (item.setores || []).join(", "),
    item.setores?.length ?? 0,
    fmtDate(item.data_relatorio || dataReferencia),
  ]);

  const ws = XLSX.utils.aoa_to_sheet([...infoRows, ...dataRows]);
  ws["!cols"] = [
    { wch: 28 },
    { wch: 42 },
    { wch: 20 },
    { wch: 18 },
  ];

  XLSX.utils.book_append_sheet(wb, ws, "Multiplos Setores");

  const safe = (dataReferencia || "relatorio").replace(/-/g, "");
  XLSX.writeFile(wb, `multiplos_setores_${safe}.xlsx`);
}
