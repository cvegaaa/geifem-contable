import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

const LINEA_VACIA = {
  producto_id: "",
  descripcion: "",
  cantidad: 1,
  costo_unitario: 0,
  tarifa_iva: 19,
};

export default function Page() {
  const [ordenes, setOrdenes] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [proveedorId, setProveedorId] = useState("");
  const [bodegaId, setBodegaId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);

  const cargar = async () => {
    try {
      const [oc, te, pr, bo] = await Promise.all([
        api.get("/api/compras/ordenes-compra"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/inventario/bodegas"),
      ]);
      setOrdenes(oc.data);
      setProveedores(te.data);
      setProductos(pr.data);
      setBodegas(bo.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const totales = useMemo(() => {
    let subtotal = 0;
    let ivaTotal = 0;
    for (const l of lineas) {
      const s = Number(l.cantidad || 0) * Number(l.costo_unitario || 0);
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
        copia[i].costo_unitario = p.costo_promedio_ponderado || 0;
      }
    }
    setLineas(copia);
  };

  const registrar = async () => {
    setError(null);
    setMensaje(null);
    setGuardando(true);
    try {
      const { data } = await api.post("/api/compras/ordenes-compra", {
        proveedor_id: proveedorId,
        fecha,
        bodega_id: bodegaId || null,
        observaciones: observaciones || null,
        items: lineas.map((l) => ({
          producto_id: l.producto_id || null,
          descripcion: l.descripcion,
          cantidad: Number(l.cantidad),
          costo_unitario: Number(l.costo_unitario),
          tarifa_iva: Number(l.tarifa_iva),
        })),
      });
      setMensaje(`Orden OC-${data.consecutivo} creada por ${fmtCOP(data.total)}`);
      setProveedorId("");
      setObservaciones("");
      setLineas([{ ...LINEA_VACIA }]);
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Órdenes de compra</h1>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-green-700">{mensaje}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
        <div className="grid gap-3 sm:grid-cols-4">
          <FormField label="Proveedor">
            <Select value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
              <option value="">Seleccione…</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Fecha">
            <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </FormField>
          <FormField label="Bodega destino (opcional)">
            <Select value={bodegaId} onChange={(e) => setBodegaId(e.target.value)}>
              <option value="">—</option>
              {bodegas.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
        </div>

        <h2 className="text-sm font-semibold text-slate-700 mt-3 mb-2">Ítems</h2>
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
              placeholder="Costo unitario"
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

        <div className="flex flex-wrap gap-6 mt-4 text-sm">
          <span>Subtotal: <b>{fmtCOP(totales.subtotal)}</b></span>
          <span>IVA: <b>{fmtCOP(totales.ivaTotal)}</b></span>
          <span className="text-geifem-navy">Total: <b>{fmtCOP(totales.total)}</b></span>
        </div>

        <button
          onClick={registrar}
          disabled={guardando || !proveedorId || !fecha}
          className="mt-4 bg-geifem-navy text-white text-sm px-4 py-2 rounded disabled:opacity-50"
        >
          {guardando ? "Guardando…" : "Crear orden"}
        </button>
      </div>

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Órdenes registradas</h2>
      <Table
        columns={[
          { key: "consecutivo", label: "N°", render: (r) => `OC-${r.consecutivo}` },
          { key: "fecha", label: "Fecha" },
          { key: "proveedor_nombre", label: "Proveedor" },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
          { key: "estado", label: "Estado" },
        ]}
        rows={ordenes}
      />
    </div>
  );
}
