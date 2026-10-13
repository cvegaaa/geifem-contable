import { Input, Select } from "../../shared/layout/FormField/index.jsx";
import { fmtCOP } from "../../shared/documentos/index.jsx";

export const lineaVentaVacia = () => ({ producto_id: "", descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 });

export function totalesVenta(lineas) {
  let subtotal = 0;
  let iva = 0;
  for (const l of lineas) {
    const sub = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
    subtotal += sub;
    iva += sub * (Number(l.tarifa_iva || 0) / 100);
  }
  return { subtotal, iva, total: subtotal + iva };
}

/**
 * Tabla de ítems de venta (factura y POS). Con `permitirLibre` se puede vender
 * un concepto sin producto del catálogo (no mueve inventario).
 */
export default function LineasVenta({ lineas, setLineas, productos, totales, permitirLibre = false, cobraIva = true }) {
  const actualizar = (i, campo, valor) => {
    setLineas((ls) =>
      ls.map((l, idx) => {
        if (idx !== i) return l;
        const nueva = { ...l, [campo]: valor };
        if (campo === "producto_id" && valor) {
          const prod = productos.find((p) => p.id === valor);
          if (prod) {
            nueva.precio_unitario = prod.precio_venta || prod.precio_referencia || 0;
            // Excluido/exento (o empresa no responsable de IVA): sin IVA.
            const sinIva = !cobraIva || (prod.tipo_iva && prod.tipo_iva !== "gravado");
            nueva.tarifa_iva = sinIva ? 0 : prod.tarifa_iva != null && prod.tarifa_iva !== "" ? Number(prod.tarifa_iva) : 19;
          }
        }
        return nueva;
      })
    );
  };

  return (
    <div className="border border-slate-200 rounded-lg overflow-x-auto mb-3">
      <table className="w-full text-sm">
        <thead className="bg-slate-100 text-slate-700">
          <tr>
            <th className="text-left px-3 py-2 min-w-56">Producto</th>
            <th className="text-right px-3 py-2 w-24">Cantidad</th>
            <th className="text-right px-3 py-2 w-32">Precio unit.</th>
            <th className="text-right px-3 py-2 w-24">IVA</th>
            <th className="text-right px-3 py-2 w-32">Total</th>
            <th className="w-8"></th>
          </tr>
        </thead>
        <tbody>
          {lineas.map((l, i) => {
            const sub = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
            return (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1">
                  <Select value={l.producto_id} onChange={(e) => actualizar(i, "producto_id", e.target.value)}>
                    <option value="">{permitirLibre ? "Concepto libre (sin inventario)" : "Seleccionar…"}</option>
                    {productos.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku ? `${p.sku} — ` : ""}{p.nombre}
                      </option>
                    ))}
                  </Select>
                  {permitirLibre && !l.producto_id && (
                    <Input
                      className="mt-1"
                      placeholder="Descripción del concepto"
                      value={l.descripcion || ""}
                      onChange={(e) => actualizar(i, "descripcion", e.target.value)}
                    />
                  )}
                </td>
                <td className="px-2 py-1">
                  <Input type="number" min="0" step="any" className="text-right" value={l.cantidad}
                    onChange={(e) => actualizar(i, "cantidad", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Input type="number" min="0" step="any" className="text-right" value={l.precio_unitario}
                    onChange={(e) => actualizar(i, "precio_unitario", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Select value={cobraIva ? l.tarifa_iva : 0} disabled={!cobraIva}
                    title={cobraIva ? "" : "Tu empresa no es responsable de IVA"}
                    onChange={(e) => actualizar(i, "tarifa_iva", e.target.value)}>
                    <option value={0}>0%</option>
                    <option value={5}>5%</option>
                    <option value={19}>19%</option>
                  </Select>
                </td>
                <td className="px-3 py-1 text-right font-medium">
                  {fmtCOP(sub * (1 + Number(l.tarifa_iva || 0) / 100))}
                </td>
                <td className="text-center">
                  <button
                    onClick={() => setLineas((ls) => ls.filter((_, idx) => idx !== i))}
                    disabled={lineas.length === 1}
                    className="text-red-500 text-xs disabled:opacity-30"
                    title="Quitar línea"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot className="bg-slate-50">
          <tr>
            <td className="px-2 py-2">
              <button onClick={() => setLineas([...lineas, lineaVentaVacia()])} className="text-xs px-2 py-1 rounded-sm border border-slate-300 bg-white">
                + Línea
              </button>
            </td>
            <td colSpan={3} className="px-3 py-2 text-right text-xs text-slate-500">
              Subtotal {fmtCOP(totales.subtotal)} · IVA {fmtCOP(totales.iva)}
            </td>
            <td className="px-3 py-2 text-right font-bold text-geifem-navy">{fmtCOP(totales.total)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
