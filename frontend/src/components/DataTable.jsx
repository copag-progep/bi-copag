export default function DataTable({
  columns,
  rows,
  emptyMessage = "Nenhum dado encontrado.",
  sortKey,
  sortDir = "asc",
  onSort,
  rowKey,
}) {
  if (!rows?.length) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => {
              const sortable = Boolean(column.sortable && onSort);
              const active = sortKey === column.key;
              return (
                <th
                  key={column.key}
                  aria-sort={sortable ? (active ? (sortDir === "asc" ? "ascending" : "descending") : "none") : undefined}
                >
                  {sortable ? (
                    <button
                      type="button"
                      className={`data-table-sort${active ? " active" : ""}`}
                      onClick={() => onSort(column.key)}
                      title={`Ordenar por ${String(column.label).toLowerCase()}`}
                    >
                      <span>{column.label}</span>
                      <span aria-hidden="true">{active ? (sortDir === "asc" ? "↑" : "↓") : "↕"}</span>
                    </button>
                  ) : column.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey?.(row, index) || row.id || row.protocolo || row.email || `${index}-${columns[0]?.key || "row"}`}>
              {columns.map((column) => {
                const value = row[column.key];
                return (
                  <td key={column.key}>
                    {column.render
                      ? column.render(value, row)
                      : Array.isArray(value)
                        ? value.join(", ")
                        : value ?? "-"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
