import { useEffect, useState } from "react";

import api from "../api/client";


function formatDate(value) {
  if (!value) return "sem dados";
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

function buildSummary(data) {
  if (!data) return "Verificando dados...";
  if (data.status === "no_data") return "Sem snapshots importados";

  const ref = formatDate(data.data_referencia_global);
  const current = data.total_setores_em_dia ?? 0;
  const expected = data.total_setores_esperados ?? 0;

  if (data.status === "ok") {
    return `Dados atualizados: ${ref} · ${current}/${expected} setores`;
  }

  if (data.setores_defasados?.length) {
    return `Atenção: ${data.setores_defasados[0]} defasado · ref. ${ref}`;
  }

  if (data.setores_ausentes?.length) {
    return `Atenção: ${data.setores_ausentes[0]} sem snapshot · ref. ${ref}`;
  }

  if (data.idade_dias > 0) {
    return `Atenção: dados de ${ref} · ${data.idade_dias} dias`;
  }

  if (data.alertas_qualidade?.length) {
    return `Atenção: qualidade do snapshot · ${ref}`;
  }

  return `Verificar dados: ${ref}`;
}

function buildDetails(data) {
  if (!data) return "Consultando frescor dos dados.";
  if (data.status === "no_data") return "Nenhum relatório foi importado neste ambiente.";

  const details = [
    `Referência global: ${formatDate(data.data_referencia_global)}`,
    `Setores em dia: ${data.total_setores_em_dia}/${data.total_setores_esperados}`,
  ];

  if (data.setores_defasados?.length) {
    details.push(`Defasados: ${data.setores_defasados.join(", ")}`);
  }
  if (data.setores_ausentes?.length) {
    details.push(`Ausentes: ${data.setores_ausentes.join(", ")}`);
  }
  if (data.alertas_qualidade?.length) {
    details.push(`Alertas de qualidade: ${data.alertas_qualidade.map((item) => item.setor).join(", ")}`);
  }

  return details.join("\n");
}


export default function DataFreshnessBadge() {
  const [freshness, setFreshness] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;

    async function loadFreshness() {
      try {
        const { data } = await api.get("/health/data-freshness");
        if (!alive) return;
        setFreshness(data);
        setError(false);
      } catch {
        if (!alive) return;
        setError(true);
      }
    }

    loadFreshness();
    const timer = window.setInterval(loadFreshness, 5 * 60 * 1000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  if (error) {
    return (
      <span className="freshness-badge attention" title="Não foi possível verificar o frescor dos dados.">
        Dados: verificar
      </span>
    );
  }

  const status = freshness?.status || "loading";
  return (
    <span className={`freshness-badge ${status}`} title={buildDetails(freshness)}>
      <span className="freshness-dot" aria-hidden="true" />
      {buildSummary(freshness)}
    </span>
  );
}
