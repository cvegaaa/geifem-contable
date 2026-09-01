import { useEffect, useState, useMemo } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";

export default function Page() {
  const { puede } = useAuth();
  const [facturas, setFacturas] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [resoluciones, setResoluciones] = useState([]);
  const [productos, setProductos] = useState([]);
  const [formasPago, setFormasPago] = useState([]);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  // Form state
  const [clienteId, setClienteId] = useState("");
  const [resolucionId, setResolucionId] = useState("");
  const [formaPagoId, setFormaPagoId] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([
    { producto_id: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 },
  ]);

  // --- Cargar datos de apoyo y listado ---
  const cargarTodo = async () => {
    try {
      const [fac, cli, res, pro, fp] = await Promise.all([
        api.get("/api/facturacion/facturas"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/configuracion/resoluciones-dian"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/configuracion/formas-pago"),
      ]);
      setFacturas(fac.data);
      setClientes(cli.data.filter((t) => t.tipo === "cliente" || !t.tipo));
      setResoluciones(res.data);
      setProductos(pro.data);
      setFormasPago(fp.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  useEffect(() => {
    cargarTodo();
  }, []);

  // --- Cálculos de totales ---
  const totales = useMemo(() => {
    let subtotal = 0;
    let ivaTotal = 0;
    for (const l of lineas) {
      const sub = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
      const iva = sub * (Number(l.tarifa_iva || 0) / 100);
      subtotal += sub;
      ivaTotal += iva;
    }
    return {
      subtotal: subtotal,
      ivaTotal: ivaTotal,
      total: subtotal + ivaTotal,
    };
  }, [lineas]);

  // --- Manejo de líneas ---
  const actualizarLinea = (i, campo, valor) => {
    const copia = [...lineas];
    copia[i] = { ...copia[i], [campo]: valor };
    // Auto-completar precio al seleccionar producto
    if (campo === "producto_id" && valor) {
      const prod = productos.find((p) => p.id === valor);
      if (prod) {
        copia[i].precio_unitario = prod.precio_referencia || prod.costo_promedio_ponderado || 0;
      }
    }
    setLineas(copia);
  };

  const agregarLinea = () => {
    setLineas([...lineas, { producto_id: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }]);
  };

  const eliminarLinea = (i) => {
    if (lineas.length === 1) return;
    setLineas(lineas.filter((_, idx) => idx !== i));
  };

  // --- Guardar factura ---
  const guardar = async () => {
    setError(null);
    setMensaje(null);

    if (!clienteId) return setError("Selecciona un cliente");
    if (!resolucionId) return setError("Selecciona una resolución DIAN");
    if (lineas.some((l) => !l.producto_id)) return setError("Todas las líneas deben tener un producto");
    if (lineas.some((l) => Number(l.cantidad) <= 0)) return setError("Las cantidades deben ser mayores a cero");

    setGuardando(true);
    try {
      const { data } = await api.post("/api/facturacion/facturas", {
        cliente_id: clienteId,
        resolucion_id: resolucionId,
        fecha: fecha,
        forma_pago_id: formaPagoId || null,
        items: lineas.map((l) => ({
          producto_id: l.producto_id,
          cantidad: Number(l.cantidad),
          precio_unitario: Number(l.precio_unitario),
          tarifa_iva: Number(l.tarifa_iva),
        })),
        observaciones: observaciones || null,
      });
      setMensaje(`Factura ${data.prefijo}${data.consecutivo} creada — Total: $${data.total.toLocaleString("es-CO")}`);
      setMostrarForm(false);
      limpiarForm();
      cargarTodo();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setGuardando(false);
    }
  };

  const limpiarForm = () => {
    setClienteId("");
    setResolucionId("");
    setFormaPagoId("");
    setFecha(new Date().toISOString().slice(0, 10));
    setObservaciones("");
    setLineas([{ producto_id: "", cantidad: 1, precio_unitario: 0, tarifa_iva: 19 }]);
  };

  const enviarDian = async (id) => {
    setError(null);
    try {
      await api.post(`/api/facturacion/facturas/${id}/enviar-dian`);
      cargarTodo();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const fmtCOP = (n) => {
    if (n == null) return "";
    return "$" + Number(n).toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  };

  // --- Render del formulario ---
  const renderForm = () => (
    <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
      <h2 className="text-lg font-bold text-geifem-navy mb-4">Nueva factura de venta</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <FormField label="Cliente">
          <Select value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
            <option value="">Seleccionar…</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre} {c.numero_documento ? `— ${c.numero_documento}` : ""}
              </option>
            ))}
          </Select>
        </FormField>

        <FormField label="Resolución DIAN">
          <Select value={resolucionId} onChange={(e) => setResolucionId(e.target.value)}>
            <option value="">Seleccionar…</option>
            {resoluciones.map((r) => (
              <option key={r.id} value={r.id}>
                {r.prefijo} — Res. {r.numero_resolucion || r.id.slice(-6)}
              </option>
            ))}
          </Select>
        </FormField>

        <FormField label="Fecha">
          <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </FormField>

        <FormField label="Forma de pago">
          <Select value={formaPagoId} onChange={(e) => setFormaPagoId(e.target.value)}>
            <option value="">Sin especificar</option>
            {formasPago.map((f) => (
              <option key={f.id} value={f.id}>{f.nombre}</option>
            ))}
          </Select>
        </FormField>
      </div>

      {/* --- Tabla de items --- */}
      <div className="border border-slate-200 rounded-lg overflow-hidden mb-4">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-700">
            <tr>
              <th className="text-left px-3 py-2">Producto</th>
              <th className="text-right px-3 py-2 w-20">Cantidad</th>
              <th className="text-right px-3 py-2 w-32">Precio unit.</th>
              <th className="text-right px-3 py-2 w-20">IVA %</th>
              <th className="text-right px-3 py-2 w-28">Subtotal</th>
              <th className="text-right px-3 py-2 w-28">IVA</th>
              <th className="text-right px-3 py-2 w-28">Total</th>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody>
            {lineas.map((l, i) => {
              const sub = Number(l.cantidad || 0) * Number(l.precio_unitario || 0);
              const iva = sub * (Number(l.tarifa_iva || 0) / 100);
              return (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-2 py-1">
                    <Select
                      value={l.producto_id}
                      onChange={(e) => actualizarLinea(i, "producto_id", e.target.value)}
                    >
                      <option value="">Seleccionar…</option>
                      {productos.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.sku ? `${p.sku} — ` : ""}{p.nombre}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-2 py-1">
                    <Input
                      type="number"
                      min="1"
                      value={l.cantidad}
                      onChange={(e) => actualizarLinea(i, "cantidad", e.target.value)}
                      className="text-right"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={l.precio_unitario}
                      onChange={(e) => actualizarLinea(i, "precio_unitario", e.target.value)}
                      className="text-right"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <Select
                      value={l.tarifa_iva}
                      onChange={(e) => actualizarLinea(i, "tarifa_iva", e.target.value)}
                    >
                      <option value={0}>0%</option>
                      <option value={5}>5%</option>
                      <option value={19}>19%</option>
                    </Select>
                  </td>
                  <td className="px-3 py-1 text-right text-slate-600">{fmtCOP(sub)}</td>
                  <td className="px-3 py-1 text-right text-slate-600">{fmtCOP(iva)}</td>
                  <td className="px-3 py-1 text-right font-medium">{fmtCOP(sub + iva)}</td>
                  <td className="px-2 py-1 text-center">
                    <button
                      onClick={() => eliminarLinea(i)}
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
              <td colSpan={4} className="px-3 py-2 text-right">Totales</td>
              <td className="px-3 py-2 text-right">{fmtCOP(totales.subtotal)}</td>
              <td className="px-3 py-2 text-right">{fmtCOP(totales.ivaTotal)}</td>
              <td className="px-3 py-2 text-right text-geifem-navy">{fmtCOP(totales.total)}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <FormField label="Observaciones">
        <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
      </FormField>

      <div className="flex gap-2 mt-4">
        <button
          onClick={agregarLinea}
          className="text-sm px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50"
        >
          + Línea
        </button>
        <button
          onClick={guardar}
          disabled={guardando}
          className="text-sm px-4 py-1.5 rounded bg-geifem-navy text-white hover:bg-geifem-blue disabled:opacity-50"
        >
          {guardando ? "Guardando…" : "Guardar factura"}
        </button>
        <button
          onClick={() => { setMostrarForm(false); limpiarForm(); }}
          className="text-sm px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50"
        >
          Cancelar
        </button>
      </div>
    </div>
  );

  // --- Render del listado ---
  const columnas = [
    {
      key: "numero",
      label: "Número",
      render: (r) => `${r.prefijo || ""}${r.consecutivo ?? ""}`,
    },
    { key: "fecha", label: "Fecha" },
    { key: "cliente_nombre", label: "Cliente" },
    {
      key: "total",
      label: "Total",
      render: (r) => fmtCOP(r.total),
    },
    { key: "estado_dian", label: "Estado DIAN" },
    {
      key: "cufe",
      label: "CUFE",
      render: (r) => (r.cufe ? r.cufe.slice(0, 12) + "…" : "—"),
    },
    {
      key: "_acciones",
      label: "",
      render: (r) =>
        puede("facturacion", "editar") && r.estado_dian === "borrador" ? (
          <button
            onClick={() => enviarDian(r.id)}
            className="text-xs text-geifem-blue hover:underline"
          >
            Enviar DIAN
          </button>
        ) : null,
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Factura de venta</h1>
        {puede("facturacion", "crear") && !mostrarForm && (
          <button
            onClick={() => setMostrarForm(true)}
            className="bg-geifem-navy text-white text-sm px-4 py-2 rounded hover:bg-geifem-blue"
          >
            + Nueva factura
          </button>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">{mensaje}</div>}

      {mostrarForm && renderForm()}

      <Table
        columns={columnas}
        rows={facturas}
        empty="No hay facturas registradas"
      />
    </div>
  );
}
