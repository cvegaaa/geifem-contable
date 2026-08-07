import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

const LINEA_VACIA = { producto_id: "", descripcion: "", cantidad: 1, costo_unitario: 0, tarifa_iva: 19 };

export default function Page() {
  const [facturas, setFacturas] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [productos, setProductos] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [form, setForm] = useState({
    proveedor_id: "",
    numero_factura: "",
    fecha: new Date().toISOString().slice(0, 10),
    fecha_vencimiento: "",
    orden_compra_id: "",
    afecta_inventario: true,
    tarifa_retefuente: 2.5,
    tarifa_reteica: 0,
    tarifa_reteiva: 0,
    observaciones: "",
  });
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);

  const cargar = async () => {
    try {
      const [fp, te, pr, oc] = await Promise.all([
        api.get("/api/compras/facturas-proveedor"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/compras/ordenes-compra"),
      ]);
      setFacturas(fp.data);
      setProveedores(te.data);
      setProductos(pr.data);
      setOrdenes(oc.data.filter((o) => o.estado !== "anulada"));
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const totales = useMemo(() => {
    let subtotal = 0;
    let iva = 0;
    for (const l of lineas) {
      const s = Number(l.cantidad || 0) * Number(l.costo_unitario || 0);
      subtotal += s;
      iva += s * (Number(l.tarifa_iva || 0) / 100);
    }
    const retefuente = (subtotal * Number(form.tarifa_retefuente || 0)) / 100;
    const reteica = (subtotal * Number(form.tarifa_reteica || 0)) / 100;
    const reteiva = (iva * Number(form.tarifa_reteiva || 0)) / 100;
    const retenciones = retefuente + reteica + reteiva;
    return {
      subtotal,
      iva,
      total: subtotal + iva,
      retefuente,
      reteica,
      reteiva,
      retenciones,
      neto: subtotal + iva - retenciones,
    };
  }, [lineas, form.tarifa_retefuente, form.tarifa_reteica, form.tarifa_reteiva]);

  const actualizarLinea = (i, campo, valor) => {
    const copia = [...lineas];
    copia[i] = { ...copia[i], [campo]: valor };
    if (campo === "producto_id" && valor) {
      const p = productos.find((x) => x.id === valor);
      if (p) {
        copia[i].descripcion = p.nombre || "";
        copia[i].costo_unitario = p.costo_promedio_ponderado || 0;
      }
    }
    setLineas(copia);
  };

  const cargarDesdeOrden = (id) => {
    setForm({ ...form, orden_compra_id: id });
    const oc = ordenes.find((o) => o.id === id);
    if (!oc) return;
    setForm((f) => ({ ...f, orden_compra_id: id, proveedor_id: oc.proveedor_id }));
    if ((oc.items || []).length) {
      setLineas(
        oc.items.map((it) => ({
          producto_id: it.producto_id || "",
          descripcion: it.descripcion,
          cantidad: it.cantidad,
          costo_unitario: it.costo_unitario,
          tarifa_iva: it.tarifa_iva,
        }))
      );
    }
  };

  const registrar = async () => {
    setError(null);
    setMensaje(null);
    setGuardando(true);
    try {
      const { data } = await api.post("/api/compras/facturas-proveedor", {
        ...form,
        orden_compra_id: form.orden_compra_id || null,
        fecha_vencimiento: form.fecha_vencimiento || null,
        observaciones: form.observaciones || null,
        tarifa_retefuente: Number(form.tarifa_retefuente),
        tarifa_reteica: Number(form.tarifa_reteica),
        tarifa_reteiva: Number(form.tarifa_reteiva),
        items: lineas.map((l) => ({
          producto_id: l.producto_id || null,
          descripcion: l.descripcion,
          cantidad: Number(l.cantidad),
          costo_unitario: Number(l.costo_unitario),
          tarifa_iva: Number(l.tarifa_iva),
        })),
      });
      setMensaje(
        `Factura ${data.numero_factura} registrada — neto a pagar ${fmtCOP(data.total_a_pagar)}`
      );
      setForm({ ...form, numero_factura: "", orden_compra_id: "", observaciones: "" });
      setLineas([{ ...LINEA_VACIA }]);
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setGuardando(false);
    }
  };

  const set = (k) => (e) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Facturas de proveedor</h1>
      <p className="text-slate-500 text-sm mb-4">
        Genera el asiento espejo (compra/inventario, IVA descontable, retenciones y cuenta por
        pagar al proveedor).
      </p>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-green-700">{mensaje}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
        <div className="grid gap-3 sm:grid-cols-4">
          <FormField label="Orden de compra (opcional)">
            <Select value={form.orden_compra_id} onChange={(e) => cargarDesdeOrden(e.target.value)}>
              <option value="">Sin orden</option>
              {ordenes.map((o) => (
                <option key={o.id} value={o.id}>
                  OC-{o.consecutivo} · {o.proveedor_nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Proveedor">
            <Select value={form.proveedor_id} onChange={set("proveedor_id")}>
              <option value="">Seleccione…</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="N° factura proveedor">
            <Input value={form.numero_factura} onChange={set("numero_factura")} />
          </FormField>
          <FormField label="Fecha">
            <Input type="date" value={form.fecha} onChange={set("fecha")} />
          </FormField>
          <FormField label="Vencimiento">
            <Input type="date" value={form.fecha_vencimiento} onChange={set("fecha_vencimiento")} />
          </FormField>
          <FormField label="ReteFuente %">
            <Input type="number" value={form.tarifa_retefuente} onChange={set("tarifa_retefuente")} />
          </FormField>
          <FormField label="ReteICA %">
            <Input type="number" value={form.tarifa_reteica} onChange={set("tarifa_reteica")} />
          </FormField>
          <FormField label="ReteIVA %">
            <Input type="number" value={form.tarifa_reteiva} onChange={set("tarifa_reteiva")} />
          </FormField>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700 mb-3">
          <input
            type="checkbox"
            checked={form.afecta_inventario}
            onChange={set("afecta_inventario")}
          />
          Afecta inventario (1435). Si se desmarca, se carga a gastos/compras (6205).
        </label>

        {lineas.map((l, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-6 items-end mb-2">
            <Select
              value={l.producto_id}
              onChange={(e) => actualizarLinea(i, "producto_id", e.target.value)}
            >
              <option value="">Producto…</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
            <Input
              placeholder="Descripción"
              value={l.descripcion}
              onChange={(e) => actualizarLinea(i, "descripcion", e.target.value)}
            />
            <Input
              type="number"
              placeholder="Cantidad"
              value={l.cantidad}
              onChange={(e) => actualizarLinea(i, "cantidad", e.target.value)}
            />
            <Input
              type="number"
              placeholder="Costo"
              value={l.costo_unitario}
              onChange={(e) => actualizarLinea(i, "costo_unitario", e.target.value)}
            />
            <Input
              type="number"
              placeholder="IVA %"
              value={l.tarifa_iva}
              onChange={(e) => actualizarLinea(i, "tarifa_iva", e.target.value)}
            />
            <button
              onClick={() => setLineas(lineas.filter((_, j) => j !== i))}
              disabled={lineas.length === 1}
              className="text-xs text-red-600 disabled:opacity-40"
            >
              Quitar
            </button>
          </div>
        ))}
        <button
          onClick={() => setLineas([...lineas, { ...LINEA_VACIA }])}
          className="text-sm text-geifem-blue hover:underline"
        >
          + Agregar ítem
        </button>

        <div className="grid gap-2 sm:grid-cols-4 mt-4 text-sm">
          <span>Subtotal: <b>{fmtCOP(totales.subtotal)}</b></span>
          <span>IVA: <b>{fmtCOP(totales.iva)}</b></span>
          <span>Retenciones: <b>-{fmtCOP(totales.retenciones)}</b></span>
          <span className="text-geifem-navy">Neto a pagar: <b>{fmtCOP(totales.neto)}</b></span>
        </div>

        <button
          onClick={registrar}
          disabled={guardando || !form.proveedor_id || !form.numero_factura}
          className="mt-4 bg-geifem-navy text-white text-sm px-4 py-2 rounded disabled:opacity-50"
        >
          {guardando ? "Registrando…" : "Registrar factura"}
        </button>
      </div>

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Facturas registradas</h2>
      <Table
        columns={[
          { key: "numero_factura", label: "Documento" },
          { key: "fecha", label: "Fecha" },
          { key: "proveedor_nombre", label: "Proveedor" },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
          {
            key: "total_retenciones",
            label: "Retenciones",
            render: (r) => fmtCOP(r.total_retenciones),
          },
          { key: "saldo_pendiente", label: "Saldo", render: (r) => fmtCOP(r.saldo_pendiente) },
          { key: "estado", label: "Estado" },
        ]}
        rows={facturas}
      />
    </div>
  );
}
