import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [docs, setDocs] = useState([]);
  const [productos, setProductos] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [formasPago, setFormasPago] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [clienteId, setClienteId] = useState("");
  const [formaPagoId, setFormaPagoId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([
    { producto_id: "", descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 },
  ]);

  const cargarTodo = async () => {
    try {
      const [dp, pr, cl, fp] = await Promise.all([
        api.get("/api/facturacion/documento-equivalente-pos"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/configuracion/formas-pago"),
      ]);
      setDocs(dp.data);
      setProductos(pr.data);
      setClientes(cl.data);
      setFormasPago(fp.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargarTodo();
  }, []);

  const totales = useMemo(() => {
    let subtotal = 0;
    let ivaTotal = 0;
    for (const l of lineas) {
      const s = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
      subtotal += s;
      ivaTotal += s * (Number(l.tarifa_iva || 0) / 100);
    }
    return { subtotal, ivaTotal, total: subtotal + ivaTotal };
  }, [lineas]);

  const actualizarLinea = (i, campo, valor) => {
    const copia = [...lineas];
    copia[i] = { ...copia[i], [campo]: valor };
    if (campo === "producto_id" && valor) {
      const p = productos.find((x) => x.id === valor);
      if (p) {
        copia[i].descripcion = p.nombre || "";
        copia[i].precio_unitario = p.precio_referencia || p.costo_promedio_ponderado || 0;
        if (p.tarifa_iva != null) copia[i].tarifa_iva = p.tarifa_iva;
      }
    }
    setLineas(copia);
  };

  const limpiar = () => {
    setClienteId("");
    setFormaPagoId("");
    setObservaciones("");
    setLineas([{ producto_id: "", descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }]);
  };

  const registrar = async () => {
    setError(null);
    setMensaje(null);
    if (lineas.some((l) => !l.descripcion.trim())) return setError("Cada línea requiere producto o descripción");
    if (lineas.some((l) => Number(l.cantidad) <= 0)) return setError("Las cantidades deben ser mayores a cero");

    setGuardando(true);
    try {
      const { data } = await api.post("/api/facturacion/documento-equivalente-pos", {
        fecha,
        cliente_id: clienteId || null,
        forma_pago_id: formaPagoId || null,
        observaciones: observaciones || null,
        items: lineas.map((l) => ({
          producto_id: l.producto_id || null,
          descripcion: l.descripcion,
          cantidad: Number(l.cantidad),
          precio_unitario: Number(l.precio_unitario),
          tarifa_iva: Number(l.tarifa_iva),
        })),
      });
      setMensaje(`Documento ${data.prefijo}-${data.consecutivo} registrado — ${fmtCOP(data.total)}`);
      limpiar();
      cargarTodo();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Documento equivalente POS</h1>
      <p className="text-sm text-slate-500 mb-4">
        Venta rápida de mostrador sin resolución DIAN. Genera asiento contable espejo.
      </p>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">{mensaje}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <FormField label="Fecha">
            <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </FormField>
          <FormField label="Cliente (opcional)">
            <Select value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
              <option value="">Consumidor final</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Forma de pago">
            <Select value={formaPagoId} onChange={(e) => setFormaPagoId(e.target.value)}>
              <option value="">Sin especificar</option>
              {formasPago.map((f) => (
                <option key={f.id} value={f.id}>{f.nombre}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
        </div>

        <div className="border border-slate-200 rounded-lg overflow-hidden mb-4">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th className="text-left px-3 py-2 w-56">Producto</th>
                <th className="text-left px-3 py-2">Descripción</th>
                <th className="text-right px-3 py-2 w-20">Cant.</th>
                <th className="text-right px-3 py-2 w-32">Precio</th>
                <th className="text-right px-3 py-2 w-20">IVA %</th>
                <th className="text-right px-3 py-2 w-28">Total</th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => {
                const s = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
                return (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1">
                      <Select value={l.producto_id} onChange={(e) => actualizarLinea(i, "producto_id", e.target.value)}>
                        <option value="">Libre…</option>
                        {productos.map((p) => (
                          <option key={p.id} value={p.id}>{p.sku ? `${p.sku} — ` : ""}{p.nombre}</option>
                        ))}
                      </Select>
                    </td>
                    <td className="px-2 py-1">
                      <Input value={l.descripcion} onChange={(e) => actualizarLinea(i, "descripcion", e.target.value)} />
                    </td>
                    <td className="px-2 py-1">
                      <Input type="number" min="0" className="text-right" value={l.cantidad} onChange={(e) => actualizarLinea(i, "cantidad", e.target.value)} />
                    </td>
                    <td className="px-2 py-1">
                      <Input type="number" min="0" step="0.01" className="text-right" value={l.precio_unitario} onChange={(e) => actualizarLinea(i, "precio_unitario", e.target.value)} />
                    </td>
                    <td className="px-2 py-1">
                      <Select value={l.tarifa_iva} onChange={(e) => actualizarLinea(i, "tarifa_iva", e.target.value)}>
                        <option value={0}>0%</option>
                        <option value={5}>5%</option>
                        <option value={19}>19%</option>
                      </Select>
                    </td>
                    <td className="px-3 py-1 text-right font-medium">
                      {fmtCOP(s * (1 + Number(l.tarifa_iva || 0) / 100))}
                    </td>
                    <td className="px-2 py-1 text-center">
                      <button
                        onClick={() => setLineas(lineas.filter((_, idx) => idx !== i))}
                        disabled={lineas.length === 1}
                        className="text-red-500 hover:text-red-700 disabled:opacity-30 text-xs"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-slate-50 font-semibold">
              <tr>
                <td colSpan={5} className="px-3 py-2 text-right">
                  Subtotal {fmtCOP(totales.subtotal)} · IVA {fmtCOP(totales.ivaTotal)}
                </td>
                <td className="px-3 py-2 text-right text-geifem-navy">{fmtCOP(totales.total)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setLineas([...lineas, { producto_id: "", descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }])}
            className="text-sm px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50"
          >
            + Línea
          </button>
          <button
            onClick={registrar}
            disabled={guardando}
            className="text-sm px-4 py-1.5 rounded bg-geifem-gold text-geifem-navy font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {guardando ? "Registrando…" : "Registrar venta POS"}
          </button>
        </div>
      </div>

      <Table
        columns={[
          { key: "numero", label: "Número", render: (r) => `${r.prefijo}-${r.consecutivo}` },
          { key: "fecha", label: "Fecha" },
          { key: "items", label: "Ítems", render: (r) => r.items?.length ?? 0 },
          { key: "subtotal", label: "Subtotal", render: (r) => fmtCOP(r.subtotal) },
          { key: "iva_total", label: "IVA", render: (r) => fmtCOP(r.iva_total) },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
        ]}
        rows={docs}
        empty="Sin documentos POS registrados"
      />
    </div>
  );
}
