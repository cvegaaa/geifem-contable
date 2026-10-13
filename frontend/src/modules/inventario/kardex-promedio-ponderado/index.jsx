import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
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

const TIPOS = { entrada: "Entrada", salida: "Salida", ajuste: "Ajuste (fija existencia)" };

export default function Page() {
  const { puede } = useAuth();
  const [productos, setProductos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [existencias, setExistencias] = useState([]);
  const [movimientos, setMovimientos] = useState([]);
  const [ajustes, setAjustes] = useState([]);
  const [productoId, setProductoId] = useState("");
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [errorForm, setErrorForm] = useState(null);
  const [form, setForm] = useState({ producto_id: "", bodega_id: "", tipo: "ajuste", cantidad: "", costo_unitario: "", fecha: hoy(), observaciones: "" });

  const nombreProducto = useMemo(() => Object.fromEntries(productos.map((p) => [p.id, p.nombre])), [productos]);
  const nombreBodega = useMemo(() => Object.fromEntries(bodegas.map((b) => [b.id, b.nombre])), [bodegas]);

  const cargar = async (pid = productoId) => {
    try {
      const q = pid ? `?producto_id=${pid}` : "";
      const [ex, mv, aj] = await Promise.all([
        api.get(`/api/inventario/kardex/existencias${q}`),
        api.get(`/api/inventario/kardex/movimientos${q}`),
        api.get("/api/inventario/kardex/ajustes"),
      ]);
      setExistencias(ex.data.filter((e) => e.cantidad !== 0));
      setMovimientos(mv.data);
      setAjustes(aj.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Ajuste anulado");
    cargar();
  });

  useEffect(() => {
    api.get("/api/inventario/catalogo-productos").then((r) => setProductos(r.data)).catch(() => {});
    api.get("/api/inventario/bodegas").then((r) => setBodegas(r.data)).catch(() => {});
    cargar("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const costoPorProducto = useMemo(
    () => Object.fromEntries(productos.map((p) => [p.id, Number(p.costo_promedio_ponderado || 0)])),
    [productos]
  );

  const filtrar = (pid) => {
    setProductoId(pid);
    cargar(pid);
  };

  const abrirAjuste = () => {
    const principal = bodegas.find((b) => b.es_principal) || bodegas[0];
    setForm({ producto_id: productoId, bodega_id: principal?.id || "", tipo: "ajuste", cantidad: "", costo_unitario: "", fecha: hoy(), observaciones: "" });
    setErrorForm(null);
    setAbierto(true);
  };

  const registrar = async () => {
    setErrorForm(null);
    if (!form.producto_id) return setErrorForm("Selecciona el producto");
    try {
      const { data } = await api.post("/api/inventario/kardex/movimientos", {
        ...form,
        cantidad: Number(form.cantidad || 0),
        costo_unitario: Number(form.costo_unitario || 0),
        observaciones: form.observaciones || null,
      });
      setAbierto(false);
      setMensaje(`Ajuste ${numeroDoc(data)} registrado`);
      const { data: prods } = await api.get("/api/inventario/catalogo-productos");
      setProductos(prods);
      cargar();
    } catch (err) {
      setErrorForm(mensajeError(err));
    }
  };

  const valorTotal = existencias.reduce((s, e) => s + e.cantidad * (costoPorProducto[e.producto_id] || 0), 0);

  return (
    <div className="max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-geifem-navy">Kardex y ajustes</h1>
          <p className="text-sm text-slate-500">Costo por promedio ponderado. Las compras y ventas mueven el kardex solas.</p>
        </div>
        <div className="flex gap-2 items-end">
          <div className="w-64">
            <Select value={productoId} onChange={(e) => filtrar(e.target.value)}>
              <option value="">Todos los productos</option>
              {productos.map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </Select>
          </div>
          {puede("inventario", "crear") && (
            <button onClick={abrirAjuste} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm whitespace-nowrap">
              + Ajuste manual
            </button>
          )}
        </div>
      </div>
      <Avisos error={error} mensaje={mensaje} />

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Existencias · valor total {fmtCOP(valorTotal)}</h2>
      <Table titulo="Existencias"
        columns={[
          { key: "producto_id", label: "Producto", render: (r) => nombreProducto[r.producto_id] || "—" },
          { key: "bodega_id", label: "Bodega", render: (r) => nombreBodega[r.bodega_id] || "—" },
          { key: "cantidad", label: "Cantidad" },
          { key: "costo", label: "Costo promedio", render: (r) => fmtCOP(costoPorProducto[r.producto_id]) },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.cantidad * (costoPorProducto[r.producto_id] || 0)) },
        ]}
        rows={existencias}
        empty="Sin existencias"
      />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Movimientos</h2>
      <Table titulo="Movimientos de inventario"
        columns={[
          { key: "fecha", label: "Fecha" },
          { key: "referencia_documento", label: "Documento" },
          { key: "producto_id", label: "Producto", render: (r) => nombreProducto[r.producto_id] || "—" },
          { key: "bodega_id", label: "Bodega", render: (r) => nombreBodega[r.bodega_id] || "—" },
          { key: "tipo", label: "Tipo", render: (r) => TIPOS[r.tipo] || r.tipo },
          { key: "cantidad", label: "Cantidad" },
          { key: "costo_unitario", label: "Costo unit.", render: (r) => fmtCOP(r.costo_unitario) },
        ]}
        rows={movimientos}
        empty="Sin movimientos"
      />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Ajustes manuales</h2>
      <Table titulo="Ajustes de inventario"
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
          { key: "fecha", label: "Fecha" },
          { key: "producto_nombre", label: "Producto" },
          { key: "tipo", label: "Tipo", render: (r) => TIPOS[r.tipo] || r.tipo },
          { key: "cantidad", label: "Cantidad" },
          { key: "observaciones", label: "Observaciones" },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acciones",
            label: "",
            render: (r) => (
              <AccionesDocumento doc={r} modulo="inventario"
                onAnular={(d) => anulacion.pedir(d, `/api/inventario/kardex/ajustes/${d.id}/anular`)} />
            ),
          },
        ]}
        rows={ajustes}
        empty="Sin ajustes manuales"
      />

      <Modal
        open={abierto}
        onClose={() => setAbierto(false)}
        title="Ajuste manual de inventario"
        footer={
          <>
            <button onClick={() => setAbierto(false)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
            <button onClick={registrar} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Registrar</button>
          </>
        }
      >
        <FormField label="Producto">
          <Select value={form.producto_id} onChange={(e) => setForm({ ...form, producto_id: e.target.value })}>
            <option value="">Seleccionar…</option>
            {productos.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </Select>
        </FormField>
        <div className="grid grid-cols-2 gap-x-3">
          <FormField label="Bodega">
            <Select value={form.bodega_id} onChange={(e) => setForm({ ...form, bodega_id: e.target.value })}>
              {bodegas.map((b) => (
                <option key={b.id} value={b.id}>{b.nombre}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Tipo">
            <Select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              {Object.entries(TIPOS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </Select>
          </FormField>
          <FormField label={form.tipo === "ajuste" ? "Existencia real (conteo)" : "Cantidad"}>
            <Input type="number" min="0" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} />
          </FormField>
          <FormField label="Costo unitario" hint={form.tipo === "salida" ? "No aplica: sale al costo promedio" : form.tipo === "ajuste" ? "Opcional" : ""}>
            <Input type="number" min="0" disabled={form.tipo === "salida"} value={form.costo_unitario}
              onChange={(e) => setForm({ ...form, costo_unitario: e.target.value })} />
          </FormField>
          <FormField label="Fecha">
            <Input type="date" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} />
          </FormField>
        </div>
        <FormField label="Observaciones">
          <Input value={form.observaciones} onChange={(e) => setForm({ ...form, observaciones: e.target.value })} />
        </FormField>
        {errorForm && <p className="text-sm text-red-600">{errorForm}</p>}
      </Modal>
      {anulacion.modal}
    </div>
  );
}
