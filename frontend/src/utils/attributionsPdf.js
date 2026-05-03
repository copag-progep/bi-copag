import jsPDF from "jspdf";
import "jspdf-autotable";

/* ── Paleta Progep / UFC ─────────────────────────── */
const NAVY   = [39,  49,  104];
const NAVY2  = [28,  35,  80];
const ORANGE = [243, 147, 32];
const YELLOW = [254, 187, 18];
const WHITE  = [255, 255, 255];
const LIGHT  = [246, 247, 252];
const BORDER = [218, 221, 238];
const INK    = [26,  32,  80];
const MUTED  = [90,  99,  144];

/* ── Cores das flags ─────────────────────────────── */
function flagRgb(days) {
  if (days >= 90) return [74,  20,  140]; // extremo
  if (days >= 60) return [183, 28,  28];  // crítico
  if (days >= 45) return [192, 57,  43];  // grave
  if (days >= 30) return [212, 117, 14];  // alerta
  if (days >= 15) return [154, 108, 0];   // atenção
  return [26, 122, 80];                   // ok
}

function flagLabel(days) {
  if (days >= 90) return "90d+";
  if (days >= 60) return "60–89d";
  if (days >= 45) return "45–59d";
  if (days >= 30) return "30–44d";
  if (days >= 15) return "15–29d";
  return "<15d";
}

/* ── Formatação de data ──────────────────────────── */
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

/* ── Truncar texto ───────────────────────────────── */
function trunc(doc, text, maxMm) {
  const lines = doc.splitTextToSize(String(text || ""), maxMm);
  return lines[0] || "";
}

/* ── Desenhar cabeçalho numa página ─────────────── */
function drawPageHeader(doc, dataReferencia, PW, ML) {
  // Fundo navy
  doc.setFillColor(...NAVY);
  doc.rect(0, 0, PW, 46, "F");

  // Detalhe: círculo decorativo (canto superior direito)
  doc.setFillColor(243, 147, 32, 0.15);
  doc.setDrawColor(243, 147, 32);
  doc.setLineWidth(0.8);
  doc.circle(PW - 18, -4, 22, "D");

  // Listra laranja inferior do cabeçalho
  doc.setFillColor(...ORANGE);
  doc.rect(0, 46, PW, 2.5, "F");

  // Badge "SEI BI"
  doc.setFillColor(243, 147, 32, 0.18);
  doc.roundedRect(ML, 8, 32, 7.5, 1.5, 1.5, "F");
  doc.setDrawColor(243, 147, 32, 0.5);
  doc.setLineWidth(0.3);
  doc.roundedRect(ML, 8, 32, 7.5, 1.5, 1.5, "D");
  doc.setTextColor(...YELLOW);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "bold");
  doc.text("SEI BI · COPAG · UFC", ML + 16, 13.5, { align: "center" });

  // Título principal
  doc.setTextColor(...WHITE);
  doc.setFontSize(19);
  doc.setFont("helvetica", "bold");
  doc.text("Relatório de Atribuições", ML, 30);

  // Subtítulo
  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(195, 202, 235);
  doc.text("Pró-Reitoria de Gestão de Pessoas · UFC", ML, 38.5);

  // Data de referência (canto direito)
  doc.setTextColor(195, 202, 235);
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.text("Data de referência", PW - 14, 27, { align: "right" });
  doc.setTextColor(...WHITE);
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.text(fmtDate(dataReferencia) || "—", PW - 14, 36, { align: "right" });
}

/* ── Desenhar rodapé numa página ─────────────────── */
function drawPageFooter(doc, pageNum, totalPages, PW, PH, ML) {
  doc.setFillColor(...NAVY);
  doc.rect(0, PH - 11, PW, 11, "F");
  doc.setFillColor(...ORANGE);
  doc.rect(0, PH - 11, PW, 1.2, "F");
  doc.setTextColor(...WHITE);
  doc.setFontSize(6.5);
  doc.setFont("helvetica", "normal");
  const gerado = new Date().toLocaleString("pt-BR");
  doc.text(`SEI BI COPAG  ·  Gerado em: ${gerado}`, ML, PH - 4);
  doc.text(`${pageNum} / ${totalPages}`, PW - ML, PH - 4, { align: "right" });
}

/* ── Função principal exportada ──────────────────── */
export function generateAttributionsPdf({ items, stats, dataReferencia, filtersText }) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const PW = 210;
  const PH = 297;
  const ML = 13;
  const MR = 13;
  const CW = PW - ML - MR; // 184 mm

  /* ── 1. CABEÇALHO ─────────────────────────────── */
  drawPageHeader(doc, dataReferencia, PW, ML);

  /* ── 2. CARDS DE ESTATÍSTICAS ─────────────────── */
  const SW = (CW - 9) / 4;
  let y = 56;
  const statCards = [
    { label: "TOTAL",           value: String(stats.total)    },
    { label: "COM ATRIBUIÇÃO",  value: String(stats.totalCom) },
    { label: "SEM ATRIBUIÇÃO",  value: String(stats.totalSem) },
    { label: "MAIOR TEMPO",     value: `${stats.maxDias}d`   },
  ];

  statCards.forEach((s, i) => {
    const sx = ML + i * (SW + 3);
    doc.setFillColor(249, 250, 255);
    doc.roundedRect(sx, y, SW, 21, 2.5, 2.5, "F");
    doc.setDrawColor(...BORDER);
    doc.setLineWidth(0.25);
    doc.roundedRect(sx, y, SW, 21, 2.5, 2.5, "D");
    // Borda laranja esquerda
    doc.setFillColor(...ORANGE);
    doc.roundedRect(sx, y, 2.5, 21, 1.5, 1.5, "F");
    // Valor
    doc.setTextColor(...NAVY);
    doc.setFontSize(13);
    doc.setFont("helvetica", "bold");
    doc.text(s.value, sx + 6, y + 12);
    // Label
    doc.setTextColor(...MUTED);
    doc.setFontSize(5.8);
    doc.setFont("helvetica", "bold");
    doc.text(s.label, sx + 6, y + 18.5);
  });

  y += 27;

  /* ── 3. FILTROS ATIVOS ────────────────────────── */
  if (filtersText) {
    doc.setFontSize(7);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(...MUTED);
    const label = `Filtros: ${filtersText}`;
    const wrapped = doc.splitTextToSize(label, CW);
    doc.text(wrapped, ML, y);
    y += wrapped.length * 4.5 + 2;
  }

  /* ── 4. TABELA ───────────────────────────────── */
  const COL_W = [48, 44, 34, 21, 20, 17]; // total = 184 = CW

  doc.autoTable({
    startY: y,
    margin: { left: ML, right: MR, bottom: 14 },
    head: [["Atribuição", "Protocolo", "Tipo", "Setor", "Desde", "Dias"]],
    body: items.map((item) => [
      item.atribuicao || "",
      item.protocolo || "",
      item.tipo || "—",
      item.setor || "",
      fmtDate(item.entrada_atribuicao),
      item.dias_com_atribuicao,
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
      0: { cellWidth: COL_W[0] },
      1: { cellWidth: COL_W[1], font: "courier", fontSize: 7 },
      2: { cellWidth: COL_W[2] },
      3: { cellWidth: COL_W[3], halign: "center" },
      4: { cellWidth: COL_W[4], halign: "center" },
      5: { cellWidth: COL_W[5], halign: "center" },
    },
    tableLineColor: BORDER,
    tableLineWidth: 0.15,
    showHead: "everyPage",

    /* Personalização de células antes de desenhar */
    didParseCell(data) {
      if (data.section !== "body") return;

      // Coluna Atribuição: itálico muted quando sem atribuição
      if (data.column.index === 0) {
        const item = items[data.row.index];
        if (!item?.atribuicao) {
          data.cell.styles.fontStyle = "italic";
          data.cell.styles.textColor = MUTED;
          data.cell.text = ["Sem atribuição"];
        }
      }
      // Coluna Dias: limpa o texto para desenho manual
      if (data.column.index === 5) {
        data.cell.text = [""];
      }
    },

    /* Desenho manual na coluna Dias */
    didDrawCell(data) {
      if (data.section !== "body" || data.column.index !== 5) return;
      const item = items[data.row.index];
      if (!item) return;

      const days = item.dias_com_atribuicao;
      const color = flagRgb(days);
      const cx = data.cell.x + 4;
      const cy = data.cell.y + data.cell.height / 2;

      doc.setFillColor(...color);
      doc.circle(cx, cy, 1.8, "F");
      doc.setTextColor(...color);
      doc.setFontSize(7.5);
      doc.setFont("helvetica", "bold");
      doc.text(`${days}d`, cx + 3.2, cy + 2.5);
    },

    /* Cabeçalho em páginas adicionais (nova página da tabela) */
    didDrawPage(data) {
      const pageNum = doc.internal.getCurrentPageInfo().pageNumber;
      if (pageNum > 1) {
        drawPageHeader(doc, dataReferencia, PW, ML);
      }
    },
  });

  /* ── 5. RODAPÉ EM TODAS AS PÁGINAS ───────────── */
  const totalPages = doc.internal.pages.length - 1;
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    drawPageFooter(doc, p, totalPages, PW, PH, ML);
  }

  /* ── 6. SALVAR ───────────────────────────────── */
  const safe = (dataReferencia || "relatorio").replace(/-/g, "");
  doc.save(`atribuicoes_${safe}.pdf`);
}
