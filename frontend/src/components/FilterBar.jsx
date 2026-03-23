import { useFilters } from "../context/FiltersContext";


export default function FilterBar() {
  const { filters, options, setFilter, clearFilters } = useFilters();

  return (
    <section className="filter-bar">
      <div className="filter-header">
        <div>
          <p className="eyebrow">Filtros</p>
          <h2>Recorte analítico</h2>
        </div>
        <button type="button" className="ghost-button" onClick={clearFilters}>
          Limpar filtros
        </button>
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
            <option value="">Todos</option>
            {[...new Set(["DIAPE", "DICAT", "DIJOR", "DICAF", "DICAF-CHEFIA", "DICAF-REPOSICOES", ...options.setores])]
              .filter(Boolean)
              .map((value) => (
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
