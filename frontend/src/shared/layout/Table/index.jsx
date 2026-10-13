import { isValidElement, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import api from "../../../core/api.js";
import { opcionDeRuta } from "../../../core/menu.js";

/** Texto plano de lo que devuelve un `render` (cadenas, números o elementos React). */
function textoDe(nodo) {
  if (nodo == null || typeof nodo === "boolean") return "";
  if (typeof nodo === "string" || typeof nodo === "number") return String(nodo);
  if (Array.isArray(nodo)) return nodo.map(textoDe).join("");
  if (isValidElement(nodo)) return textoDe(nodo.props?.children);
  return "";
}

/** Valor de una celda: el número crudo si lo hay (para que Excel pueda sumar), si no el texto mostrado. */
function valorCelda(columna, fila) {
  const crudo = fila[columna.key];
  if (typeof crudo === "number") return crudo;
  const mostrado = columna.render ? textoDe(columna.render(fila)) : crudo;
  return mostrado == null ? "" : mostrado;
}

const exportables = (columnas) => columnas.filter((c) => c.label && !String(c.key).startsWith("_"));

export async function exportarExcel(titulo, columnas, filas, resumen) {
  const cols = exportables(columnas);
  const { data } = await api.post(
    "/api/exportar/xlsx",
    {
      titulo,
      columnas: cols.map((c) => ({ key: c.key, label: c.label })),
      filas: filas.map((f) => Object.fromEntries(cols.map((c) => [c.key, valorCelda(c, f)]))),
      resumen: resumen || null,
    },
    { responseType: "blob" }
  );
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${titulo.replace(/[^\w.-]+/g, "_")}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Tabla compartida: búsqueda, paginación y exportación a Excel.
 * - `titulo`: nombre del archivo exportado (por defecto, el de la opción del menú).
 * - `exportar={false}` desactiva el botón; `porPagina` fija el tamaño de página inicial.
 */
export default function Table({ columns, rows, empty = "Sin registros", titulo, exportar = true, porPagina = 25, resumen }) {
  const { pathname } = useLocation();
  const [busqueda, setBusqueda] = useState("");
  const [pagina, setPagina] = useState(0);
  const [tamano, setTamano] = useState(porPagina);
  const [exportando, setExportando] = useState(false);

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return rows;
    const cols = exportables(columns);
    return rows.filter((r) => cols.some((c) => String(valorCelda(c, r)).toLowerCase().includes(q)));
  }, [rows, busqueda, columns]);

  useEffect(() => setPagina(0), [busqueda, rows.length, tamano]);

  const paginas = Math.max(1, Math.ceil(filtradas.length / tamano));
  const visibles = filtradas.slice(pagina * tamano, pagina * tamano + tamano);
  const mostrarBuscador = rows.length > 8;
  const nombre = titulo || opcionDeRuta(pathname)?.titulo || "Datos";

  const descargar = async () => {
    setExportando(true);
    try {
      await exportarExcel(nombre, columns, filtradas, resumen);
    } finally {
      setExportando(false);
    }
  };

  return (
    <div>
      {(mostrarBuscador || (exportar && rows.length > 0)) && (
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2 no-imprimir">
          {mostrarBuscador ? (
            <input
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar…"
              className="border border-slate-300 rounded-sm px-3 py-1.5 text-sm w-full sm:w-64 focus:ring-2 focus:ring-geifem-blue focus:outline-hidden"
            />
          ) : (
            <span />
          )}
          {exportar && rows.length > 0 && (
            <button
              onClick={descargar}
              disabled={exportando}
              className="text-xs border border-slate-300 rounded-sm px-3 py-1.5 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              title="Descargar esta tabla en Excel"
            >
              {exportando ? "Generando…" : "Exportar a Excel"}
            </button>
          )}
        </div>
      )}
      <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-700">
            <tr>
              {columns.map((c) => (
                <th key={c.key} className="text-left px-3 py-2 font-semibold whitespace-nowrap">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibles.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center text-slate-400 py-6">
                  {rows.length > 0 ? "Ningún resultado coincide con la búsqueda" : empty}
                </td>
              </tr>
            ) : (
              visibles.map((r, i) => (
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
      {filtradas.length > 10 && (
        <div className="flex flex-wrap items-center justify-between gap-2 mt-2 text-xs text-slate-500 no-imprimir">
          <span>
            {filtradas.length} registros · página {pagina + 1} de {paginas}
          </span>
          <div className="flex items-center gap-2">
            <select value={tamano} onChange={(e) => setTamano(Number(e.target.value))} className="border border-slate-300 rounded-sm px-1 py-1">
              {[25, 50, 100].map((n) => (
                <option key={n} value={n}>{n} por página</option>
              ))}
            </select>
            <button disabled={pagina === 0} onClick={() => setPagina(pagina - 1)} className="border border-slate-300 rounded-sm px-2 py-1 disabled:opacity-40">‹ Anterior</button>
            <button disabled={pagina >= paginas - 1} onClick={() => setPagina(pagina + 1)} className="border border-slate-300 rounded-sm px-2 py-1 disabled:opacity-40">Siguiente ›</button>
          </div>
        </div>
      )}
    </div>
  );
}
