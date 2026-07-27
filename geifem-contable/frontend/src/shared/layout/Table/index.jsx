export default function Table({ columns, rows, empty = "Sin registros" }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-100 text-slate-700">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className="text-left px-3 py-2 font-semibold">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-center text-slate-400 py-6">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={r.id || i} className="border-t border-slate-100 hover:bg-slate-50">
                {columns.map((c) => (
                  <td key={c.key} className="px-3 py-2">
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
