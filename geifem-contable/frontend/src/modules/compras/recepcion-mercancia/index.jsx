import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

const LINEA_VACIA = { producto_id: "", cantidad: 1, costo_unitario: 0 };

export default function Page() {
  const [recepciones, setRecepciones] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [ordenId, setOrdenId] = useState("");
  const [bodegaId, setBodegaId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);

  const cargar = async () => {
    try {
      const [re, oc, pr, bo] = await Promise.all([
        api.get("/api/compras/recepcion-mercancia"),
        api.get("/api/compras/ordenes-compra"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/inventario/bodegas"),
      ]);
      setRecepciones(re.data);
      setOrdenes(oc.data.filter((o) => o.estado === "abierta"));
      setProductos(pr.data);
      setBodegas(bo.data);
      const principal = bo.data.find((b) => b.es_principal) || bo.data[0];
      if (principal) setBodegaId((prev) => prev || principal.id);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const total = useMemo(
    () =>
      lineas.reduce(
        (acc, l) => acc + Number(l.cantidad || 0) * Number(l.costo_unitario || 0),
        0
      ),
    [lineas]
  );

  const cargarDesdeOrden = (id) => {
    setOrdenId(id);
    const oc = ordenes.find((o) => o.id === id);
    if (!oc) return;
    if (oc.bodega_id) setBodegaId(oc.bodega_id);
    const items = (oc.items || [])
      .filter((it) => it.producto_id)
      .map((it) => ({
        producto_id: it.producto_id,
        cantidad: it.cantidad,
        costo_unitario: it.costo_unitario,
      }));
    if (items.length) setLineas(items);
  };

  const actualizarLinea = (i, campo, valor) => {
    const copia = [...lineas];
    copia[i] = { ...copia[i], [campo]: valor };
    if (campo === "producto_id" && valor) {
      const p = productos.find((x) => x.id === valor);
      if (p) copia[i].costo_unitario = p.costo_promedio_ponderado || 0;
    }
    setLineas(copia);
  };

  const registrar = async () => {
    setError(null);
    setMensaje(null);
    setGuardando(true);
    try {
      const { data } = await api.post("/api/compras/recepcion-mercancia", {
        orden_compra_id: ordenId || null,
        bodega_id: bodegaId,
        fecha,
        observaciones: observaciones || null,
        items: lineas.map((l) => ({
          producto_id: l.producto_id,
          cantidad: Number(l.cantidad),
          costo_unitario: Number(l.costo_unitario),
        })),
      });
      setMensaje(
        `${data.referencia} registrada — entrada a bodega ${data.bodega_nombre} por ${fmtCOP(
          data.valor_total
        )}`
      );
      setOrdenId("");
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
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Recepción de mercancía</h1>
      <p className="text-slate-500 text-sm mb-4">
        Cada recepción genera entradas de inventario en la bodega seleccionada y recalcula el
        costo promedio ponderado.
      </p>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-green-700">{mensaje}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
        <div className="grid gap-3 sm:grid-cols-4">
          <FormField label="Orden de compra (opcional)">
            <Select value={ordenId} onChange={(e) => cargarDesdeOrden(e.target.value)}>
              <option value="">Sin orden</option>
              {ordenes.map((o) => (
                <option key={o.id} value={o.id}>
                  OC-{o.consecutivo} · {o.proveedor_nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Bodega">
            <Select value={bodegaId} onChange={(e) => setBodegaId(e.target.value)}>
              <option value="">Seleccione…</option>
              {bodegas.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.nombre}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Fecha">
            <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </FormField>
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
        </div>

        {lineas.map((l, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-4 items-end mb-2">
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

        <div className="mt-4 text-sm text-geifem-navy">
          Valor recibido: <b>{fmtCOP(total)}</b>
        </div>
        <button
          onClick={registrar}
          disabled={guardando || !bodegaId || lineas.some((l) => !l.producto_id)}
          className="mt-3 bg-geifem-navy text-white text-sm px-4 py-2 rounded disabled:opacity-50"
        >
          {guardando ? "Registrando…" : "Registrar recepción"}
        </button>
      </div>

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Recepciones registradas</h2>
      <Table
        columns={[
          { key: "referencia", label: "Documento" },
          { key: "fecha", label: "Fecha" },
          { key: "bodega_nombre", label: "Bodega" },
          { key: "items", label: "Ítems", render: (r) => (r.items || []).length },
          { key: "valor_total", label: "Valor", render: (r) => fmtCOP(r.valor_total) },
        ]}
        rows={recepciones}
      />
    </div>
  );
}
