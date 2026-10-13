import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import {
  AccionesDocumento,
  Avisos,
  EstadoBadge,
  fmtCOP,
  hoy,
  mensajeError,
  numeroDoc,
  useAnulacion,
} from "../../../shared/documentos/index.jsx";

export default function Page() {
  const { puede } = useAuth();
  const [lista, setLista] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [abierto, setAbierto] = useState(false);
  const [facturaId, setFacturaId] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [motivo, setMotivo] = useState("");
  const [lineas, setLineas] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const [dv, fp] = await Promise.all([
        api.get("/api/compras/devoluciones-proveedor"),
        api.get("/api/compras/facturas-proveedor"),
      ]);
      setLista(dv.data);
      setFacturas(fp.data.filter((f) => f.estado !== "anulado"));
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); }, []);
  const anulacion = useAnulacion(() => { setMensaje("Devolución anulada: se restableció el saldo de la factura y el inventario"); cargar(); });

  const elegirFactura = (id) => {
    setFacturaId(id);
    const f = facturas.find((x) => x.id === id);
    setLineas((f?.items || []).map((it) => ({ ...it, devolver: 0 })));
  };

  const totales = useMemo(() => {
    let sub = 0;
    let iva = 0;
    for (const l of lineas) {
      const s = Number(l.devolver || 0) * Number(l.costo_unitario || 0);
      sub += s;
      iva += s * (Number(l.tarifa_iva || 0) / 100);
    }
    return { sub, iva, total: sub + iva };
  }, [lineas]);

  const guardar = async () => {
    setError(null);
    const items = lineas.filter((l) => Number(l.devolver) > 0).map((l) => ({
      producto_id: l.producto_id || null, descripcion: l.descripcion || l.producto_nombre || "Ítem", cantidad: Number(l.devolver),
      costo_unitario: Number(l.costo_unitario), tarifa_iva: Number(l.tarifa_iva || 0),
    }));
    if (!facturaId) return setError("Selecciona la factura del proveedor");
    if (!motivo.trim()) return setError("Indica el motivo de la devolución");
    if (!items.length) return setError("Indica la cantidad a devolver en al menos un ítem");
    try {
      const { data } = await api.post("/api/compras/devoluciones-proveedor", { factura_id: facturaId, fecha, motivo, items });
      setMensaje(`Devolución ${data.numero} registrada: reduce la deuda en ${fmtCOP(data.neto)}`);
      setAbierto(false);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Devoluciones a proveedor</h1>
        {puede("compras", "crear") && !abierto && (
          <button onClick={() => { setAbierto(true); setFacturaId(""); setLineas([]); setMotivo(""); setFecha(hoy()); setError(null); setMensaje(null); }}
            className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">+ Nueva devolución</button>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-4">
        Devuelves mercancía o te rebajan una factura: baja lo que debes al proveedor, sale la mercancía del inventario y se revierten el IVA descontable y las retenciones en la misma proporción.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {abierto && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField label="Factura del proveedor">
              <Select value={facturaId} onChange={(e) => elegirFactura(e.target.value)}>
                <option value="">Seleccionar…</option>
                {facturas.map((f) => <option key={f.id} value={f.id}>{f.numero_factura} — {f.proveedor_nombre} — saldo {fmtCOP(f.saldo_pendiente)}</option>)}
              </Select>
            </FormField>
            <FormField label="Fecha"><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></FormField>
            <FormField label="Motivo"><Input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Defecto, error de despacho…" /></FormField>
          </div>
          {lineas.length > 0 && (
            <div className="border border-slate-200 rounded-lg overflow-x-auto mb-3">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr><th className="text-left px-3 py-2">Ítem</th><th className="text-right px-3 py-2">Facturado</th><th className="text-right px-3 py-2">Costo unit.</th><th className="text-right px-3 py-2 w-32">Devolver</th></tr>
                </thead>
                <tbody>
                  {lineas.map((l, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-1">{l.descripcion || l.producto_nombre}</td>
                      <td className="px-3 py-1 text-right">{l.cantidad}</td>
                      <td className="px-3 py-1 text-right">{fmtCOP(l.costo_unitario)}</td>
                      <td className="px-2 py-1">
                        <Input type="number" className="text-right" value={l.devolver}
                          onChange={(e) => setLineas((ls) => ls.map((x, k) => (k === i ? { ...x, devolver: e.target.value } : x)))} />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-50">
                  <tr><td colSpan={3} className="px-3 py-2 text-right text-xs text-slate-500">Subtotal {fmtCOP(totales.sub)} · IVA {fmtCOP(totales.iva)}</td>
                    <td className="px-3 py-2 text-right font-bold text-geifem-navy">{fmtCOP(totales.total)}</td></tr>
                </tfoot>
              </table>
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={guardar} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white">Registrar devolución</button>
            <button onClick={() => setAbierto(false)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}

      <Table
        titulo="Devoluciones a proveedor"
        columns={[
          { key: "numero", label: "Número", render: (r) => <b>{numeroDoc(r)}</b> },
          { key: "fecha", label: "Fecha" },
          { key: "proveedor_nombre", label: "Proveedor" },
          { key: "factura_numero", label: "Factura" },
          { key: "motivo", label: "Motivo" },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
          { key: "neto", label: "Reduce deuda", render: (r) => fmtCOP(r.neto) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          { key: "_acc", label: "", render: (r) => <AccionesDocumento doc={r} modulo="compras" onAnular={(d) => anulacion.pedir(d, `/api/compras/devoluciones-proveedor/${d.id}/anular`)} /> },
        ]}
        rows={lista}
        empty="Sin devoluciones registradas"
      />
      {anulacion.modal}
    </div>
  );
}
