import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { useEmpresa } from "../../../core/EmpresaContext.jsx";
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
import LineasVenta, { lineaVentaVacia, totalesVenta } from "../_LineasVenta.jsx";

export default function Page() {
  const { puede } = useAuth();
  const { perfil } = useEmpresa();
  const [docs, setDocs] = useState([]);
  const [productos, setProductos] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [formasPago, setFormasPago] = useState([]);
  const [cajas, setCajas] = useState([]);
  const [cajaId, setCajaId] = useState("");
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [fecha, setFecha] = useState(hoy());
  const [clienteId, setClienteId] = useState("");
  const [formaPagoId, setFormaPagoId] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([lineaVentaVacia()]);

  const cargar = async () => {
    try {
      const [dp, pr, cl, fp, cj] = await Promise.all([
        api.get("/api/facturacion/documento-equivalente-pos"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/configuracion/formas-pago"),
        api.get("/api/tesoreria/caja"),
      ]);
      setCajas(cj.data);
      setDocs(dp.data);
      setProductos(pr.data);
      setClientes(cl.data.filter((t) => t.tipo !== "proveedor"));
      setFormasPago(fp.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Documento POS anulado");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const totales = useMemo(() => totalesVenta(lineas), [lineas]);

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    setFecha(doc && m === "editar" ? doc.fecha : hoy());
    setCajaId(doc?.caja_id || cajas[0]?.id || "");
    setClienteId(doc?.cliente_id || "");
    setFormaPagoId(doc?.forma_pago_id || "");
    setObservaciones(doc?.observaciones || "");
    setLineas(
      doc
        ? doc.items.map((it) => ({
            producto_id: it.producto_id || "",
            descripcion: it.producto_id ? "" : it.descripcion,
            cantidad: it.cantidad,
            precio_unitario: it.precio_unitario,
            tarifa_iva: it.tarifa_iva,
          }))
        : [lineaVentaVacia()]
    );
  };

  const guardar = async () => {
    setError(null);
    if (lineas.some((l) => !l.producto_id && !(l.descripcion || "").trim()))
      return setError("Cada línea necesita un producto o una descripción");
    if (!cajaId) return setError("Crea primero una caja en Tesorería › Caja");
    const cuerpo = {
      fecha,
      caja_id: cajaId,
      cliente_id: clienteId || null,
      forma_pago_id: formaPagoId || null,
      observaciones: observaciones || null,
      items: lineas.map((l) => ({
        producto_id: l.producto_id || null,
        descripcion: l.producto_id ? null : l.descripcion,
        cantidad: Number(l.cantidad),
        precio_unitario: Number(l.precio_unitario),
        tarifa_iva: Number(l.tarifa_iva),
      })),
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/facturacion/documento-equivalente-pos/${origen.id}`, cuerpo)
          : await api.post("/api/facturacion/documento-equivalente-pos", cuerpo);
      setMensaje(`${numeroDoc(data)} ${modo === "editar" ? "actualizado" : "registrado"} — Total ${fmtCOP(data.total)}`);
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
    { key: "cliente_nombre", label: "Cliente" },
    { key: "caja_nombre", label: "Caja" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="pos"
          doc={r}
          modulo="facturacion"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/facturacion/documento-equivalente-pos/${d.id}/anular`)}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Documento POS</h1>
        {puede("facturacion", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nueva venta POS
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-1">{tituloModo(modo, "documento POS", origen)}</h2>
          <p className="text-xs text-slate-500 mb-4">
            Venta de contado: el dinero entra a la caja elegida y los productos salen de la bodega principal.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-2">
            <FormField label="Caja">
              <Select value={cajaId} onChange={(e) => setCajaId(e.target.value)}>
                {cajas.length === 0 && <option value="">Sin cajas</option>}
                {cajas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre}</option>
                ))}
              </Select>
            </FormField>
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
          </div>
          <LineasVenta lineas={lineas} setLineas={setLineas} productos={productos} totales={totales} permitirLibre cobraIva={perfil?.cobra_iva !== false} />
          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
          <div className="flex gap-2 mt-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Registrar venta"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">
              Cancelar
            </button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={docs} empty="No hay ventas POS registradas" />
      {anulacion.modal}
    </div>
  );
}
