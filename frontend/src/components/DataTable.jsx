export default function DataTable({ columns, rows, emptyMessage = "Nenhum dado encontrado." }) {
  if (!rows?.length) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id || row.protocolo || row.email || `${index}-${columns[0]?.key || "row"}`}>
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
