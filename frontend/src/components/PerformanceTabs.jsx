import WorkspaceTabs from "./WorkspaceTabs";


export default function PerformanceTabs() {
  return (
    <WorkspaceTabs
      label="Visões de desempenho"
      tabs={[
        { to: "/entradas-saidas", label: "Fluxo", icon: "↔" },
        { to: "/movimentacoes", label: "Movimentações", icon: "≡" },
        { to: "/produtividade", label: "Produtividade", icon: "↗" },
      ]}
    />
  );
}
