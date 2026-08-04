import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [notas, setNotas] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [tipo, setTipo] = useState("credito");
  const [facturaId, setFacturaId] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [motivo, setMotivo] = useState("");
  const [lineas, setLineas] = useState([
    { descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 },
  ]);

  const cargarTodo = async () => {
    try {
      const [nt, fc] = await Promise.all([
        api.get("/api/facturacion/notas-credito-debito"),
        api.get("/api/facturacion/facturas"),
      ]);
      setNotas(nt.data);
      setFacturas(fc.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargarTodo();
  }, []);

  const facturaSel = facturas.find((f) => f.id === facturaId);

  // Al elegir factura origen, precargar sus items como base editable
  const elegirFactura = (id) => {
    setFacturaId(id);
    const f = facturas.find((x) => x.id === id);
    if (f?.items?.length) {
      setLineas(
        f.items.map((it) => ({
          descripcion: it.descripcion || `Item ${it.producto_id?.slice(-6) || ""}`,
          cantidad: it.cantidad,
          precio_unitario: it.precio_unitario,
          tarifa_iva: it.tarifa_iva,
        })),
      );
    }
  };

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
    setLineas(copia);
  };

  const limpiar = () => {
    setTipo("credito");
    setFacturaId("");
    setMotivo("");
    setFecha(new Date().toISOString().slice(0, 10));
    setLineas([{ descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }]);
  };

  const guardar = async () => {
    setError(null);
    setMensaje(null);
    if (!facturaId) return setError("Selecciona la factura origen");
    if (!motivo.trim()) return setError("Indica el motivo de la nota");
    if (lineas.some((l) => !l.descripcion.trim())) return setError("Cada línea requiere descripción");
    if (lineas.some((l) => Number(l.cantidad) <= 0)) return setError("Las cantidades deben ser mayores a cero");

    setGuardando(true);
    try {
      const { data } = await api.post("/api/facturacion/notas-credito-debito", {
        factura_id: facturaId,
        tipo,
        fecha,
        motivo,
        items: lineas.map((l) => ({
          descripcion: l.descripcion,
          cantidad: Number(l.cantidad),
          precio_unitario: Number(l.precio_unitario),
          tarifa_iva: Number(l.tarifa_iva),
        })),
      });
      setMensaje(`Nota ${data.prefijo}${data.consecutivo} creada — ${fmtCOP(data.total)}`);
      setMostrarForm(false);
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
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-geifem-navy">Notas crédito / débito</h1>
          <p className="text-sm text-slate-500">
            La nota crédito reversa el asiento de la factura; la nota débito lo incrementa.
          </p>
        </div>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="text-sm px-4 py-2 rounded bg-geifem-navy text-white hover:bg-geifem-blue"
        >
          {mostrarForm ? "Cancelar" : "+ Nueva nota"}
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">{mensaje}</div>}

      {mostrarForm && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <FormField label="Tipo de nota">
              <Select value={tipo} onChange={(e) => setTipo(e.target.value)}>
                <option value="credito">Crédito (NC)</option>
                <option value="debito">Débito (ND)</option>
              </Select>
            </FormField>

            <FormField label="Factura origen">
              <Select value={facturaId} onChange={(e) => elegirFactura(e.target.value)}>
                <option value="">Seleccionar…</option>
                {facturas.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.prefijo}{f.consecutivo} — {f.cliente_nombre} — {fmtCOP(f.total)}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Fecha">
              <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </FormField>

            <FormField label="Motivo">
              <Input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Devolución, descuento…" />
            </FormField>
          </div>

          {facturaSel && (
            <p className="text-xs text-slate-500 -mt-1 mb-3">
              Cliente: <strong>{facturaSel.cliente_nombre}</strong> · Total factura: {fmtCOP(facturaSel.total)}
            </p>
          )}

          <div className="border border-slate-200 rounded-lg overflow-hidden mb-4">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-slate-700">
                <tr>
                  <th className="text-left px-3 py-2">Concepto</th>
                  <th className="text-right px-3 py-2 w-20">Cant.</th>
                  <th className="text-right px-3 py-2 w-32">Valor unit.</th>
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
                  <td colSpan={4} className="px-3 py-2 text-right">
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
              onClick={() => setLineas([...lineas, { descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }])}
              className="text-sm px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50"
            >
              + Línea
            </button>
            <button
              onClick={guardar}
              disabled={guardando}
              className="text-sm px-4 py-1.5 rounded bg-geifem-navy text-white hover:bg-geifem-blue disabled:opacity-50"
            >
              {guardando ? "Guardando…" : "Guardar nota"}
            </button>
          </div>
        </div>
      )}

      <Table
        columns={[
          { key: "numero", label: "Número", render: (r) => `${r.prefijo}${r.consecutivo}` },
          { key: "tipo", label: "Tipo" },
          { key: "fecha", label: "Fecha" },
          { key: "factura_numero", label: "Factura origen" },
          { key: "cliente_nombre", label: "Cliente" },
          { key: "motivo", label: "Motivo" },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
        ]}
        rows={notas}
        empty="Sin notas registradas"
      />
    </div>
  );
}
