import jsPDF from "jspdf";
import "jspdf-autotable";

const NAVY = [39, 49, 104];
const NAVY2 = [28, 35, 80];
const ORANGE = [243, 147, 32];
const YELLOW = [254, 187, 18];
const WHITE = [255, 255, 255];
const LIGHT = [246, 247, 252];
const BORDER = [218, 221, 238];
const INK = [26, 32, 80];
const MUTED = [90, 99, 144];

function fmtDate(value) {
  if (!value) return "-";
  try {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
      new Date(`${value}T00:00:00Z`)
    );
  } catch {
    return value;
  }
}

function drawPageHeader(doc, dataReferencia, PW, ML) {
  doc.setFillColor(...NAVY);
  doc.rect(0, 0, PW, 46, "F");

  doc.setFillColor(243, 147, 32, 0.15);
  doc.setDrawColor(243, 147, 32);
  doc.setLineWidth(0.8);
  doc.circle(PW - 18, -4, 22, "D");

  doc.setFillColor(...ORANGE);
  doc.rect(0, 46, PW, 2.5, "F");

  doc.setFillColor(243, 147, 32, 0.18);
  doc.roundedRect(ML, 8, 32, 7.5, 1.5, 1.5, "F");
  doc.setDrawColor(243, 147, 32, 0.5);
  doc.setLineWidth(0.3);
  doc.roundedRect(ML, 8, 32, 7.5, 1.5, 1.5, "D");
  doc.setTextColor(...YELLOW);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "bold");
  doc.text("ANALYTICSEI · COPAG · UFC", ML + 16, 13.5, { align: "center" });

  doc.setTextColor(...WHITE);
  doc.setFontSize(18);
  doc.setFont("helvetica", "bold");
  doc.text("Relatório de Múltiplos Setores", ML, 30);

  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(195, 202, 235);
  doc.text("Pró-Reitoria de Gestão de Pessoas · UFC", ML, 38.5);

  doc.setTextColor(195, 202, 235);
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.text("Data de referência", PW - 14, 27, { align: "right" });
  doc.setTextColor(...WHITE);
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.text(fmtDate(dataReferencia), PW - 14, 36, { align: "right" });
}

function drawPageFooter(doc, pageNum, totalPages, PW, PH, ML) {
  doc.setFillColor(...NAVY);
  doc.rect(0, PH - 11, PW, 11, "F");
  doc.setFillColor(...ORANGE);
  doc.rect(0, PH - 11, PW, 1.2, "F");
  doc.setTextColor(...WHITE);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "normal");
  const gerado = new Date().toLocaleString("pt-BR");
  doc.text(`AnalyticSEI  ·  Gerado em: ${gerado}`, ML, PH - 4);
  doc.text(`${pageNum} / ${totalPages}`, PW - ML, PH - 4, { align: "right" });
}

export function generateMultiSectorPdf({ items, stats, dataReferencia, filtersText }) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const PW = 210;
  const PH = 297;
  const ML = 13;
  const MR = 13;
  const CW = PW - ML - MR;

  drawPageHeader(doc, dataReferencia, PW, ML);

  const SW = (CW - 9) / 4;
  let y = 56;
  const statCards = [
    { label: "TOTAL", value: String(stats.total) },
    { label: "EM 2 SETORES", value: String(stats.em2) },
    { label: "3+ SETORES", value: String(stats.em3mais) },
    { label: "SETORES ENVOLVIDOS", value: String(stats.setoresUnicos) },
  ];

  statCards.forEach((s, i) => {
    const sx = ML + i * (SW + 3);
    doc.setFillColor(249, 250, 255);
    doc.roundedRect(sx, y, SW, 21, 2.5, 2.5, "F");
    doc.setDrawColor(...BORDER);
    doc.setLineWidth(0.25);
    doc.roundedRect(sx, y, SW, 21, 2.5, 2.5, "D");
    doc.setFillColor(...ORANGE);
    doc.roundedRect(sx, y, 2.5, 21, 1.5, 1.5, "F");
    doc.setTextColor(...NAVY);
    doc.setFontSize(13);
    doc.setFont("helvetica", "bold");
    doc.text(s.value, sx + 6, y + 12);
    doc.setTextColor(...MUTED);
    doc.setFontSize(5.8);
    doc.setFont("helvetica", "bold");
    doc.text(s.label, sx + 6, y + 18.5);
  });

  y += 27;

  if (filtersText) {
    doc.setFontSize(7);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...MUTED);
    const wrapped = doc.splitTextToSize(`Filtros: ${filtersText}`, CW);
    doc.text(wrapped, ML, y);
    y += wrapped.length * 4.5 + 2;
  }

  doc.autoTable({
    startY: y,
    margin: { left: ML, right: MR, bottom: 14, top: 52 },
    head: [["Protocolo", "Setores", "Qtd", "Data do relatório"]],
    body: items.map((item) => [
      item.protocolo || "",
      (item.setores || []).join(", "),
      item.setores?.length ?? 0,
      fmtDate(item.data_relatorio || dataReferencia),
    ]),
    headStyles: {
      fillColor: NAVY,
      textColor: WHITE,
      fontStyle: "bold",
      fontSize: 7.5,
      cellPadding: { top: 3.5, bottom: 3.5, left: 3, right: 2 },
    },
    bodyStyles: {
      textColor: INK,
      fontSize: 7.5,
      cellPadding: { top: 2.8, bottom: 2.8, left: 3, right: 2 },
    },
    alternateRowStyles: { fillColor: LIGHT },
    columnStyles: {
      0: { cellWidth: 45, font: "courier", fontSize: 7 },
      1: { cellWidth: 84 },
      2: { cellWidth: 18, halign: "center", fontStyle: "bold" },
      3: { cellWidth: 37, halign: "center" },
    },
    tableLineColor: BORDER,
    tableLineWidth: 0.15,
    showHead: "everyPage",
    didDrawPage() {
      const pageNum = doc.internal.getCurrentPageInfo().pageNumber;
      if (pageNum > 1) {
        drawPageHeader(doc, dataReferencia, PW, ML);
      }
    },
  });

  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i += 1) {
    doc.setPage(i);
    drawPageFooter(doc, i, totalPages, PW, PH, ML);
  }

  const safe = (dataReferencia || "relatorio").replace(/-/g, "");
  doc.save(`multiplos_setores_${safe}.pdf`);
}
