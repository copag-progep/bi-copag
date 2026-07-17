import { useFilters } from "../context/FiltersContext";


export default function FilterBar() {
  const { filters, options, optionsLoading, setFilter, clearFilters } = useFilters();

  const setorRestrito = options.setor_restrito === true;
  const setoresVisiveis = setorRestrito
    ? (options.setores_do_usuario || [])
    : [...new Set(["DIAPE", "DICAT", "DIJOR", "DICAF", "DICAF-CHEFIA", "DICAF-REPOSICOES", ...options.setores])].filter(Boolean);
  const hasActiveFilters = Boolean(
    filters.data_inicial || filters.data_final || filters.setor || filters.tipo || filters.atribuicao
  );

  return (
    <section className="filter-bar">
      <div className="filter-header">
        <div>
          <p className="eyebrow">Filtros</p>
          <h2>Recorte operacional</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {setorRestrito && setoresVisiveis.length > 0 && (
            <span style={{
              fontSize: "0.78rem", fontWeight: 700, color: "var(--primary)",
              background: "rgba(39,49,104,.08)", padding: "4px 10px", borderRadius: 8,
              border: "1px solid rgba(39,49,104,.18)",
            }}>
              Visualizando: {setoresVisiveis.join(" · ")}
            </span>
          )}
          {setorRestrito && setoresVisiveis.length === 0 && (
            <span style={{
              fontSize: "0.78rem", fontWeight: 700, color: "#bf3535",
              background: "rgba(191,53,53,.08)", padding: "4px 10px", borderRadius: 8,
            }}>
              Sem acesso a divisões
            </span>
          )}
          {optionsLoading ? <span className="filter-loading">Atualizando opções...</span> : null}
          {hasActiveFilters ? (
            <button type="button" className="ghost-button" onClick={clearFilters}>Limpar filtros</button>
          ) : null}
        </div>
      </div>

      <div className="filter-grid">
        <label className="field">
          <span>Data de referência</span>
          <select value={filters.data_referencia} onChange={(event) => setFilter("data_referencia", event.target.value)}>
            <option value="">Última data disponível</option>
            {options.datas.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Data inicial</span>
          <input
            type="date"
            value={filters.data_inicial}
            onChange={(event) => setFilter("data_inicial", event.target.value)}
          />
        </label>

        <label className="field">
          <span>Data final</span>
          <input
            type="date"
            value={filters.data_final}
            onChange={(event) => setFilter("data_final", event.target.value)}
          />
        </label>

        <label className="field">
          <span>Setor</span>
          <select value={filters.setor} onChange={(event) => setFilter("setor", event.target.value)}>
            <option value="">{setorRestrito ? "Todos os meus setores" : "Todos"}</option>
            {setoresVisiveis.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Tipo de processo</span>
          <select value={filters.tipo} onChange={(event) => setFilter("tipo", event.target.value)}>
            <option value="">Todos</option>
            {options.tipos.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Atribuição</span>
          <select value={filters.atribuicao} onChange={(event) => setFilter("atribuicao", event.target.value)}>
            <option value="">Todas</option>
            <option value="__sem_atribuicao__">Sem atribuição</option>
            {options.atribuicoes.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
