import { useEffect, useState } from "react";

export default function LoadingBlock({ label = "Carregando...", slowThreshold = 6000 }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowThreshold);
    return () => clearTimeout(timer);
  }, [slowThreshold]);

  return (
    <div className="loading-card">
      <div className="loading-spinner" />
      <p className="loading-label">{label}</p>
      {slow ? (
        <p className="loading-hint">
          O servidor está iniciando. Isso pode levar alguns segundos na primeira visita do dia.
        </p>
      ) : null}
    </div>
  );
}
