import jsPDF from "jspdf";
import "jspdf-autotable";

/* ── Paleta ─────────────────────────────────────── */
const NAVY   = [39,  49,  104];
const ORANGE = [243, 147, 32];
const LIGHT  = [246, 247, 252];
const BORDER = [218, 221, 238];
const INK    = [26,  32,  80];
const MUTED  = [90,  99,  144];
const GREEN  = [26,  122, 80];
const RED    = [191, 53, 53];
const WHITE  = [255, 255, 255];

const RISCO_COLORS = {
  critico:  [191, 53,  53],
  elevado:  [212, 117, 14],
  moderado: [138, 91,  0],
  normal:   [26,  122, 80],
};

const STATUS_LABELS = {
  pendente:          "Pendente",
  em_acompanhamento: "Em acompanhamento",
  saiu_do_setor:     "Resolvido (auto)",
  resolvido_manual:  "Resolvido (manual)",
  arquivado:         "Arquivado",
};

function fmtDate(value) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
      new Date(`${value}T00:00:00Z`)
    );
  } catch {
    return value;
  }
}

function hojeFortaleza() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Fortaleza" }).format(new Date());
}

function diffDias(value) {
  if (!value) return null;
  const MS_DIA = 86400000;
  return Math.round((Date.parse(`${value}T00:00:00Z`) - Date.parse(`${hojeFortaleza()}T00:00:00Z`)) / MS_DIA);
}

function diasPrazoLabel(value) {
  const d = diffDias(value);
  if (d === null) return "—";
  return `${d < 0 ? "-" : "+"}${String(Math.abs(d)).padStart(3, "0")}`;
}

function nivelLabel(nivel) {
  if (!nivel) return "—";
  return nivel.charAt(0).toUpperCase() + nivel.slice(1);
}

/**
 * Gera PDF da pauta da sessão selecionada usando jsPDF + autotable.
 *
 * @param {object} sessao  Objeto retornado por GET /api/pauta/sessoes/{id}
 */
export function generatePautaPdf(sessao) {
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const pageW  = doc.internal.pageSize.getWidth();
  const pageH  = doc.internal.pageSize.getHeight();
  const margin = 14;
  let y = margin;

  /* ── Cabeçalho ───────────────────────────────── */
  doc.setFillColor(...NAVY);
  doc.rect(0, 0, pageW, 22, "F");

  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...WHITE);
  doc.text("AnalyticSEI · Pauta Prioritária", margin, 10);

  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.text(
    `Gerado em ${new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date())}`,
    pageW - margin,
    10,
    { align: "right" }
  );
  y = 28;

  /* ── Título e período da sessão ─────────────── */
  doc.setFontSize(13);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...INK);
  doc.text(sessao.titulo, margin, y);
  y += 7;

  doc.setFontSize(8.5);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(...MUTED);

  const periodo = sessao.data_fim
    ? `Início: ${fmtDate(sessao.data_inicio)}  ·  Prazo da pauta: ${fmtDate(sessao.data_fim)}`
    : `Início: ${fmtDate(sessao.data_inicio)}  ·  Sem prazo definido`;
  const reuniao = sessao.data_reuniao ? `  ·  Reunião: ${fmtDate(sessao.data_reuniao)}` : "";
  doc.text(periodo + reuniao, margin, y);
  y += 5;

  if (sessao.observacoes) {
    doc.setTextColor(...INK);
    doc.text(`Observações: ${sessao.observacoes}`, margin, y);
    y += 5;
  }

  /* ── KPIs de resumo ─────────────────────────── */
  const contagens = sessao.contagens || {};
  const total = (sessao.itens || []).length;
  const ativos = (contagens.pendente || 0) + (contagens.em_acompanhamento || 0);
  const resolvidos = (contagens.saiu_do_setor || 0) + (contagens.resolvido_manual || 0);

  const kpis = [
    { label: "Total",            value: total,                       color: NAVY },
    { label: "Pendentes",        value: contagens.pendente || 0,     color: [138, 91, 0] },
    { label: "Em acompanhamento",value: contagens.em_acompanhamento || 0, color: NAVY },
    { label: "Resolvidos",       value: resolvidos,                  color: GREEN },
    { label: "Arquivados",       value: contagens.arquivado || 0,    color: MUTED },
  ];

  y += 2;
  const kpiW = (pageW - margin * 2) / kpis.length;
  kpis.forEach((kpi, i) => {
    const x = margin + i * kpiW;
    doc.setFillColor(...LIGHT);
    doc.roundedRect(x, y, kpiW - 3, 14, 2, 2, "F");
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...kpi.color);
    doc.text(String(kpi.value), x + kpiW / 2 - 1.5, y + 7, { align: "center" });
    doc.setFontSize(6.5);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...MUTED);
    doc.text(kpi.label, x + kpiW / 2 - 1.5, y + 12, { align: "center" });
  });
  y += 20;

  /* ── Tabela de itens ─────────────────────────── */
  // Ordenar: ativos primeiro (pendente, em_acompanhamento), depois resolvidos, arquivados
  const ORDER = { pendente: 0, em_acompanhamento: 1, saiu_do_setor: 2, resolvido_manual: 3, arquivado: 4 };
  const itens = [...(sessao.itens || [])].sort(
    (a, b) => (ORDER[a.status] ?? 5) - (ORDER[b.status] ?? 5) || (b.score_risco ?? 0) - (a.score_risco ?? 0)
  );

  const columns = [
    { header: "Protocolo",    dataKey: "protocolo" },
    { header: "Setor",        dataKey: "setor" },
    { header: "Tipo",         dataKey: "tipo" },
    { header: "Dias",         dataKey: "dias" },
    { header: "Risco",        dataKey: "nivel" },
    { header: "Responsável",  dataKey: "responsavel" },
    { header: "Status",       dataKey: "status" },
    { header: "Prazo",        dataKey: "prazo" },
    { header: "Dias prazo",   dataKey: "diasPrazo" },
    { header: "Nota da gestão", dataKey: "nota" },
  ];

  const rows = itens.map((item) => {
    const diasPrazo = diasPrazoLabel(item.prazo);
    return {
      protocolo:  item.protocolo,
      setor:      item.setor,
      tipo:       item.tipo || "—",
      dias:       item.dias_no_setor != null ? `${item.dias_no_setor}d` : "—",
      nivel:      nivelLabel(item.nivel_risco),
      responsavel: item.assigned_to_nome || "—",
      status:     STATUS_LABELS[item.status] || item.status,
      prazo:      fmtDate(item.prazo),
      diasPrazo,
      nota:       item.nota_admin || "—",
      _nivel:     item.nivel_risco,
      _status:    item.status,
      _score:     item.score_risco,
      _diasPrazoDelta: diffDias(item.prazo),
    };
  });

  doc.autoTable({
    startY:  y,
    head:    [columns.map((c) => c.header)],
    body:    rows.map((r) => columns.map((c) => r[c.dataKey])),
    theme:   "grid",
    margin:  { left: margin, right: margin },
    styles: {
      fontSize: 7.5,
      cellPadding: 2.5,
      textColor: INK,
      font: "helvetica",
    },
    headStyles: {
      fillColor: NAVY,
      textColor: WHITE,
      fontStyle: "bold",
      fontSize: 7.5,
    },
    alternateRowStyles: { fillColor: LIGHT },
    columnStyles: {
      0: { cellWidth: 34, fontStyle: "bold" },
      1: { cellWidth: 18 },
      2: { cellWidth: 38 },
      3: { cellWidth: 12, halign: "center" },
      4: { cellWidth: 18, halign: "center" },
      5: { cellWidth: 28 },
      6: { cellWidth: 28, halign: "center" },
      7: { cellWidth: 20, halign: "center" },
      8: { cellWidth: 18, halign: "center", fontStyle: "bold" },
      9: { cellWidth: "auto" },
    },
    willDrawCell: (data) => {
      if (data.section !== "body") return;
      const row = rows[data.row.index];
      if (!row) return;

      // Colorir coluna Risco
      if (data.column.index === 4 && row._nivel) {
        const rgb = RISCO_COLORS[row._nivel];
        if (rgb) {
          doc.setTextColor(...rgb);
          doc.setFont("helvetica", "bold");
        }
      }

      // Colorir coluna Status
      if (data.column.index === 6) {
        if (row._status === "saiu_do_setor" || row._status === "resolvido_manual") {
          doc.setTextColor(...GREEN);
          doc.setFont("helvetica", "bold");
        } else if (row._status === "pendente") {
          doc.setTextColor(138, 91, 0);
        } else if (row._status === "arquivado") {
          doc.setTextColor(...MUTED);
        }
      }

      // Colorir coluna Dias prazo
      if (data.column.index === 8 && row._diasPrazoDelta !== null) {
        doc.setTextColor(...(row._diasPrazoDelta < 0 ? RED : GREEN));
        doc.setFont("helvetica", "bold");
      }
    },
  });

  /* ── Rodapé em todas as páginas ─────────────── */
  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...MUTED);
    doc.setDrawColor(...BORDER);
    doc.line(margin, pageH - 8, pageW - margin, pageH - 8);
    doc.text("AnalyticSEI · Pauta Prioritária", margin, pageH - 4);
    doc.text(`Página ${i}/${totalPages}`, pageW - margin, pageH - 4, { align: "right" });
  }

  const slug = sessao.titulo
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .slice(0, 40);
  doc.save(`pauta_${slug}.pdf`);
}
