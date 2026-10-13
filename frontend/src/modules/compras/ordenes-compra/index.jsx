import { useEffect, useState } from "react";
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
import LineasCompra, { itemsAFormulario, lineaCompraVacia } from "../_LineasCompra.jsx";

export default function Page() {
  const { puede } = useAuth();
  const [ordenes, setOrdenes] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(hoy());
  const [proveedorId, setProveedorId] = useState("");
  const [bodegaId, setBodegaId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([lineaCompraVacia()]);

  const cargar = async () => {
    try {
      const [oc, te, pr, bo] = await Promise.all([
        api.get("/api/compras/ordenes-compra"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/inventario/bodegas"),
      ]);
      setOrdenes(oc.data);
      setProveedores(te.data.filter((t) => t.tipo !== "cliente"));
      setProductos(pr.data);
      setBodegas(bo.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Orden anulada");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    setFecha(doc && m === "editar" ? doc.fecha : hoy());
    setProveedorId(doc?.proveedor_id || "");
    setBodegaId(doc?.bodega_id || "");
    setObservaciones(doc?.observaciones || "");
    setLineas(doc ? itemsAFormulario(doc.items) : [lineaCompraVacia()]);
  };

  const guardar = async () => {
    setError(null);
    if (!proveedorId) return setError("Selecciona el proveedor");
    if (lineas.some((l) => !l.producto_id && !l.descripcion.trim())) return setError("Cada línea necesita producto o descripción");
    const cuerpo = {
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
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/compras/ordenes-compra/${origen.id}`, cuerpo)
          : await api.post("/api/compras/ordenes-compra", cuerpo);
      setMensaje(`Orden ${numeroDoc(data)} ${modo === "editar" ? "actualizada" : "creada"} por ${fmtCOP(data.total)}`);
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
    { key: "fecha", label: "Fecha" },
    { key: "proveedor_nombre", label: "Proveedor" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="orden_compra"
          doc={r}
          modulo="compras"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/compras/ordenes-compra/${d.id}/anular`)}
          bloqueo={r.estado !== "abierta" && r.estado !== "anulado" ? "Ya tiene entradas o facturas asociadas" : null}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Órdenes de compra</h1>
        {puede("compras", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nueva orden
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-3">{tituloModo(modo, "orden de compra", origen)}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField label="Proveedor">
              <Select value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
                <option value="">Seleccionar…</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
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
                  <option key={b.id} value={b.id}>{b.nombre}</option>
                ))}
              </Select>
            </FormField>
          </div>
          <LineasCompra lineas={lineas} setLineas={setLineas} productos={productos} />
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
          <div className="flex gap-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Crear orden"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={ordenes} empty="No hay órdenes de compra" />
      {anulacion.modal}
    </div>
  );
}
