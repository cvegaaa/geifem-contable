import { Input, Select } from "../../shared/layout/FormField/index.jsx";
import { fmtCOP } from "../../shared/documentos/index.jsx";

export const lineaCompraVacia = () => ({
  producto_id: "", descripcion: "", cantidad: 1, costo_unitario: 0, tarifa_iva: 19, concepto_retefuente_id: "",
});

export function totalesCompra(lineas) {
  let subtotal = 0;
  let iva = 0;
  for (const l of lineas) {
    const s = Number(l.cantidad || 0) * Number(l.costo_unitario || 0);
    subtotal += s;
    iva += s * (Number(l.tarifa_iva || 0) / 100);
  }
  return { subtotal, iva, total: subtotal + iva };
}

/** Copia los ítems de un documento para cargarlos en el formulario. */
export const itemsAFormulario = (items = []) =>
  items.map((it) => ({
    producto_id: it.producto_id || "",
    descripcion: it.descripcion || it.producto_nombre || "",
    cantidad: it.cantidad,
    costo_unitario: it.costo_unitario,
    tarifa_iva: it.tarifa_iva ?? 0,
    concepto_retefuente_id: it.concepto_retefuente_id || "",
  }));

/**
 * Ítems de compra. `soloProductos`: exige producto del catálogo (entradas de
 * mercancía). `conIva`: muestra la columna de IVA.
 */
export default function LineasCompra({
  lineas, setLineas, productos, soloProductos = false, conIva = true, cobraIva = true,
  conceptos = null, // si se pasa, cada línea elige su concepto de ReteFuente
}) {
  const actualizar = (i, campo, valor) =>
    setLineas((ls) =>
      ls.map((l, idx) => {
        if (idx !== i) return l;
        const nueva = { ...l, [campo]: valor };
        if (campo === "producto_id" && valor) {
          const p = productos.find((x) => x.id === valor);
          if (p) {
            nueva.descripcion = p.nombre || "";
            if (!Number(l.costo_unitario)) nueva.costo_unitario = p.costo_promedio_ponderado || 0;
            if (conceptos && p.concepto_retefuente_compra_id) nueva.concepto_retefuente_id = p.concepto_retefuente_compra_id;
          }
        }
        return nueva;
      })
    );

  const { subtotal, iva, total } = totalesCompra(conIva ? lineas : lineas.map((l) => ({ ...l, tarifa_iva: 0 })));

  return (
    <div className="border border-slate-200 rounded-lg overflow-x-auto mb-3">
      <table className="w-full text-sm">
        <thead className="bg-slate-100">
          <tr>
            <th className="text-left px-3 py-2 min-w-56">{soloProductos ? "Producto" : "Producto o concepto"}</th>
            <th className="text-right px-3 py-2 w-24">Cantidad</th>
            <th className="text-right px-3 py-2 w-32">Costo unit.</th>
            {conIva && <th className="text-right px-3 py-2 w-24">IVA</th>}
            {conceptos && <th className="text-left px-3 py-2 w-56">Retención en la fuente</th>}
            <th className="text-right px-3 py-2 w-32">Total</th>
            <th className="w-8"></th>
          </tr>
        </thead>
        <tbody>
          {lineas.map((l, i) => {
            const s = Number(l.cantidad || 0) * Number(l.costo_unitario || 0);
            return (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1">
                  <Select value={l.producto_id} onChange={(e) => actualizar(i, "producto_id", e.target.value)}>
                    <option value="">{soloProductos ? "Seleccionar…" : "Concepto libre (gasto o servicio)"}</option>
                    {productos.map((p) => (
                      <option key={p.id} value={p.id}>{p.sku ? `${p.sku} — ` : ""}{p.nombre}</option>
                    ))}
                  </Select>
                  {!soloProductos && !l.producto_id && (
                    <Input className="mt-1" placeholder="Descripción" value={l.descripcion}
                      onChange={(e) => actualizar(i, "descripcion", e.target.value)} />
                  )}
                </td>
                <td className="px-2 py-1">
                  <Input type="number" min="0" step="any" className="text-right" value={l.cantidad}
                    onChange={(e) => actualizar(i, "cantidad", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Input type="number" min="0" step="any" className="text-right" value={l.costo_unitario}
                    onChange={(e) => actualizar(i, "costo_unitario", e.target.value)} />
                </td>
                {conIva && (
                  <td className="px-2 py-1">
                    <Select value={l.tarifa_iva} onChange={(e) => actualizar(i, "tarifa_iva", e.target.value)}>
                      <option value={0}>0%</option>
                      <option value={5}>5%</option>
                      <option value={19}>19%</option>
                    </Select>
                  </td>
                )}
                {conceptos && (
                  <td className="px-2 py-1">
                    <Select value={l.concepto_retefuente_id || ""} onChange={(e) => actualizar(i, "concepto_retefuente_id", e.target.value)}>
                      <option value="">Sin retención</option>
                      {conceptos.map((c) => (
                        <option key={c.id} value={c.id}>{c.nombre} ({c.tarifa}%)</option>
                      ))}
                    </Select>
                  </td>
                )}
                <td className="px-3 py-1 text-right font-medium">
                  {fmtCOP(s * (conIva ? 1 + Number(l.tarifa_iva || 0) / 100 : 1))}
                </td>
                <td className="text-center">
                  <button onClick={() => setLineas((ls) => ls.filter((_, idx) => idx !== i))} disabled={lineas.length === 1}
                    className="text-red-500 text-xs disabled:opacity-30" title="Quitar línea">✕</button>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot className="bg-slate-50">
          <tr>
            <td className="px-2 py-2">
              <button onClick={() => setLineas([...lineas, lineaCompraVacia()])} className="text-xs px-2 py-1 rounded-sm border border-slate-300 bg-white">
                + Línea
              </button>
            </td>
            <td colSpan={(conIva ? 3 : 2) + (conceptos ? 1 : 0)} className="px-3 py-2 text-right text-xs text-slate-500">
              {conIva ? `Subtotal ${fmtCOP(subtotal)} · IVA ${fmtCOP(iva)}` : ""}
            </td>
            <td className="px-3 py-2 text-right font-bold text-geifem-navy">{fmtCOP(total)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
