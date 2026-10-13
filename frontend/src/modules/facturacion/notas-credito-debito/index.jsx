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
  tituloModo,
  useAnulacion,
} from "../../../shared/documentos/index.jsx";

const lineaVacia = () => ({ descripcion: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19, producto_id: null, inventariable: false, reingresar: false });

export default function Page() {
  const { puede } = useAuth();
  const [notas, setNotas] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [tipo, setTipo] = useState("credito");
  const [facturaId, setFacturaId] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [motivo, setMotivo] = useState("");
  const [lineas, setLineas] = useState([lineaVacia()]);

  const cargar = async () => {
    try {
      const [nt, fc] = await Promise.all([
        api.get("/api/facturacion/notas-credito-debito"),
        api.get("/api/facturacion/facturas"),
      ]);
      setNotas(nt.data);
      setFacturas(fc.data.filter((f) => f.estado !== "anulado"));
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Nota anulada: se restableció el saldo de la factura");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const facturaSel = facturas.find((f) => f.id === facturaId);

  const elegirFactura = (id) => {
    setFacturaId(id);
    const f = facturas.find((x) => x.id === id);
    if (f?.items?.length) {
      setLineas(
        f.items.map((it) => ({
          descripcion: it.descripcion || "Ítem facturado",
          cantidad: it.cantidad,
          precio_unitario: it.precio_unitario,
          tarifa_iva: it.tarifa_iva,
          producto_id: it.producto_id || null,
          inventariable: Boolean(it.inventariable),
          reingresar: false,
        }))
      );
    }
  };

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    setTipo(doc?.tipo || "credito");
    setFacturaId(doc?.factura_id || "");
    setFecha(doc && m === "editar" ? doc.fecha : hoy());
    setMotivo(doc?.motivo || "");
    setLineas(
      doc
        ? doc.items.map((it) => ({
            descripcion: it.descripcion,
            cantidad: it.cantidad,
            precio_unitario: it.precio_unitario,
            tarifa_iva: it.tarifa_iva,
            producto_id: it.producto_id || null,
            inventariable: Boolean(it.producto_id),
            reingresar: Boolean(it.reingresar),
          }))
        : [lineaVacia()]
    );
  };

  const totales = useMemo(() => {
    let subtotal = 0;
    let iva = 0;
    for (const l of lineas) {
      const s = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
      subtotal += s;
      iva += s * (Number(l.tarifa_iva || 0) / 100);
    }
    return { subtotal, iva, total: subtotal + iva };
  }, [lineas]);

  const actualizar = (i, campo, valor) =>
    setLineas((ls) => ls.map((l, idx) => (idx === i ? { ...l, [campo]: valor } : l)));

  const guardar = async () => {
    setError(null);
    if (!facturaId) return setError("Selecciona la factura origen");
    if (!motivo.trim()) return setError("Indica el motivo de la nota");
    if (lineas.some((l) => !l.descripcion.trim())) return setError("Cada línea requiere descripción");
    const cuerpo = {
      factura_id: facturaId,
      tipo,
      fecha,
      motivo,
      items: lineas.map((l) => ({
        descripcion: l.descripcion,
        cantidad: Number(l.cantidad),
        precio_unitario: Number(l.precio_unitario),
        tarifa_iva: Number(l.tarifa_iva),
        producto_id: tipo === "credito" && l.reingresar ? l.producto_id : null,
        reingresar: tipo === "credito" && Boolean(l.reingresar),
      })),
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/facturacion/notas-credito-debito/${origen.id}`, cuerpo)
          : await api.post("/api/facturacion/notas-credito-debito", cuerpo);
      setMensaje(`Nota ${numeroDoc(data)} ${modo === "editar" ? "actualizada" : "creada"} — ${fmtCOP(data.total)}`);
      setModo(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  };

  const columnas = [
    { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
    { key: "tipo", label: "Tipo", render: (r) => (r.tipo === "credito" ? "Crédito" : "Débito") },
    { key: "fecha", label: "Fecha" },
    { key: "factura_numero", label: "Factura" },
    { key: "cliente_nombre", label: "Cliente" },
    { key: "motivo", label: "Motivo" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "total_retenciones", label: "Retenciones", render: (r) => (r.total_retenciones ? fmtCOP(r.total_retenciones) : "—") },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="nota"
          doc={r}
          modulo="facturacion"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/facturacion/notas-credito-debito/${d.id}/anular`)}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-geifem-navy">Notas crédito y débito</h1>
          <p className="text-sm text-slate-500">
            La nota crédito disminuye el saldo de la factura (devoluciones, descuentos); la débito lo aumenta. Las retenciones, la autorretención y el impuesto al consumo se trasladan en la misma proporción de la factura.
          </p>
        </div>
        {puede("facturacion", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">
            + Nueva nota
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-3">{tituloModo(modo, "nota", origen)}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <FormField label="Tipo de nota">
              <Select value={tipo} disabled={modo === "editar"} onChange={(e) => setTipo(e.target.value)}>
                <option value="credito">Nota crédito (NC)</option>
                <option value="debito">Nota débito (ND)</option>
              </Select>
            </FormField>
            <FormField label="Factura origen">
              <Select value={facturaId} onChange={(e) => elegirFactura(e.target.value)}>
                <option value="">Seleccionar…</option>
                {facturas.map((f) => (
                  <option key={f.id} value={f.id}>
                    {numeroDoc(f)} — {f.cliente_nombre} — saldo {fmtCOP(f.saldo_pendiente)}
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
            <p className="text-xs text-slate-500 mb-2">
              Factura {numeroDoc(facturaSel)}: total {fmtCOP(facturaSel.total)}, saldo pendiente {fmtCOP(facturaSel.saldo_pendiente)}.
            </p>
          )}
          <div className="border border-slate-200 rounded-lg overflow-x-auto mb-3">
            <table className="w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="text-left px-3 py-2">Descripción</th>
                  <th className="text-right px-3 py-2 w-24">Cantidad</th>
                  <th className="text-right px-3 py-2 w-32">Valor unit.</th>
                  <th className="text-right px-3 py-2 w-24">IVA</th>
                  {tipo === "credito" && <th className="px-3 py-2 w-28 text-center" title="La mercancía vuelve a la bodega al costo con que salió">Reingresa</th>}
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {lineas.map((l, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1"><Input value={l.descripcion} onChange={(e) => actualizar(i, "descripcion", e.target.value)} /></td>
                    <td className="px-2 py-1"><Input type="number" className="text-right" value={l.cantidad} onChange={(e) => actualizar(i, "cantidad", e.target.value)} /></td>
                    <td className="px-2 py-1"><Input type="number" className="text-right" value={l.precio_unitario} onChange={(e) => actualizar(i, "precio_unitario", e.target.value)} /></td>
                    <td className="px-2 py-1">
                      <Select value={l.tarifa_iva} onChange={(e) => actualizar(i, "tarifa_iva", e.target.value)}>
                        <option value={0}>0%</option>
                        <option value={5}>5%</option>
                        <option value={19}>19%</option>
                      </Select>
                    </td>
                    {tipo === "credito" && (
                      <td className="text-center">
                        {l.inventariable ? (
                          <input type="checkbox" checked={l.reingresar} onChange={(e) => actualizar(i, "reingresar", e.target.checked)} />
                        ) : <span className="text-slate-300">—</span>}
                      </td>
                    )}
                    <td className="text-center">
                      <button onClick={() => setLineas((ls) => ls.filter((_, idx) => idx !== i))} disabled={lineas.length === 1}
                        className="text-red-500 text-xs disabled:opacity-30">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50">
                <tr>
                  <td className="px-2 py-2">
                    <button onClick={() => setLineas([...lineas, lineaVacia()])} className="text-xs px-2 py-1 rounded-sm border border-slate-300 bg-white">+ Línea</button>
                  </td>
                  <td colSpan={2} className="px-3 py-2 text-right text-xs text-slate-500">
                    Subtotal {fmtCOP(totales.subtotal)} · IVA {fmtCOP(totales.iva)}
                  </td>
                  <td className="px-3 py-2 text-right font-bold text-geifem-navy">{fmtCOP(totales.total)}</td>
                  <td></td>
                  {tipo === "credito" && <td></td>}
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="flex gap-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Guardar nota"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={notas} empty="No hay notas registradas" />
      {anulacion.modal}
    </div>
  );
}
