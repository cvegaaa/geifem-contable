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
  const [recepciones, setRecepciones] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(hoy());
  const [ordenId, setOrdenId] = useState("");
  const [bodegaId, setBodegaId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([lineaCompraVacia()]);

  const cargar = async () => {
    try {
      const [re, oc, pr, bo] = await Promise.all([
        api.get("/api/compras/recepcion-mercancia"),
        api.get("/api/compras/ordenes-compra"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/inventario/bodegas"),
      ]);
      setRecepciones(re.data);
      setOrdenes(oc.data.filter((o) => o.estado !== "anulado"));
      setProductos(pr.data);
      setBodegas(bo.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Entrada anulada: se retiraron sus unidades del inventario");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const bodegaPrincipal = () => (bodegas.find((b) => b.es_principal) || bodegas[0])?.id || "";

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    setFecha(doc && m === "editar" ? doc.fecha : hoy());
    setOrdenId(doc?.orden_compra_id || "");
    setBodegaId(doc?.bodega_id || bodegaPrincipal());
    setObservaciones(doc?.observaciones || "");
    setLineas(doc ? itemsAFormulario(doc.items) : [lineaCompraVacia()]);
  };

  const cargarDesdeOrden = (id) => {
    setOrdenId(id);
    const oc = ordenes.find((o) => o.id === id);
    if (!oc) return;
    if (oc.bodega_id) setBodegaId(oc.bodega_id);
    const items = itemsAFormulario((oc.items || []).filter((it) => it.producto_id));
    if (items.length) setLineas(items);
  };

  const guardar = async () => {
    setError(null);
    if (!bodegaId) return setError("Selecciona la bodega");
    if (lineas.some((l) => !l.producto_id)) return setError("Cada línea debe tener un producto del catálogo");
    const cuerpo = {
      orden_compra_id: ordenId || null,
      bodega_id: bodegaId,
      fecha,
      observaciones: observaciones || null,
      items: lineas.map((l) => ({
        producto_id: l.producto_id,
        cantidad: Number(l.cantidad),
        costo_unitario: Number(l.costo_unitario),
      })),
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/compras/recepcion-mercancia/${origen.id}`, cuerpo)
          : await api.post("/api/compras/recepcion-mercancia", cuerpo);
      setMensaje(`Entrada ${numeroDoc(data)} ${modo === "editar" ? "actualizada" : "registrada"} en ${data.bodega_nombre} por ${fmtCOP(data.valor_total)}`);
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
    { key: "bodega_nombre", label: "Bodega" },
    { key: "items", label: "Productos", render: (r) => r.items?.map((i) => `${i.producto_nombre} ×${i.cantidad}`).join(", ") },
    { key: "valor_total", label: "Valor", render: (r) => fmtCOP(r.valor_total) },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="entrada"
          doc={r}
          modulo="compras"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/compras/recepcion-mercancia/${d.id}/anular`)}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Entradas de mercancía</h1>
        {puede("compras", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nueva entrada
          </button>
        )}
      </div>
      <p className="text-slate-500 text-sm mb-4">
        Cada entrada suma existencias en la bodega y recalcula el costo promedio ponderado.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-3">{tituloModo(modo, "entrada de mercancía", origen)}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField label="Orden de compra (opcional)">
              <Select value={ordenId} onChange={(e) => cargarDesdeOrden(e.target.value)}>
                <option value="">Sin orden</option>
                {ordenes.map((o) => (
                  <option key={o.id} value={o.id}>
                    {numeroDoc(o)} — {o.proveedor_nombre} ({o.estado})
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Bodega">
              <Select value={bodegaId} onChange={(e) => setBodegaId(e.target.value)}>
                {bodegas.map((b) => (
                  <option key={b.id} value={b.id}>{b.nombre}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Fecha">
              <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </FormField>
          </div>
          <LineasCompra lineas={lineas} setLineas={setLineas} productos={productos} soloProductos conIva={false} />
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
          <div className="flex gap-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Registrar entrada"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={recepciones} empty="No hay entradas de mercancía" />
      {anulacion.modal}
    </div>
  );
}
