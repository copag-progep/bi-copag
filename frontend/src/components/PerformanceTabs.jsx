import WorkspaceTabs from "./WorkspaceTabs";


export default function PerformanceTabs() {
  return (
    <WorkspaceTabs
      label="Visões de desempenho"
      tabs={[
        { to: "/entradas-saidas", label: "Fluxo", icon: "↔" },
        { to: "/produtividade", label: "Produtividade", icon: "↗" },
      ]}
    />
  );
}
