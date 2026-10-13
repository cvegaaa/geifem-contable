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
  const [facturas, setFacturas] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [resoluciones, setResoluciones] = useState([]);
  const [productos, setProductos] = useState([]);
  const [formasPago, setFormasPago] = useState([]);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const [clienteId, setClienteId] = useState("");
  const [resolucionId, setResolucionId] = useState("");
  const [formaPagoId, setFormaPagoId] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [vencimiento, setVencimiento] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [lineas, setLineas] = useState([lineaVentaVacia()]);

  const cargar = async () => {
    try {
      const [fac, cli, res, pro, fp] = await Promise.all([
        api.get("/api/facturacion/facturas"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/configuracion/resoluciones-dian"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/configuracion/formas-pago"),
      ]);
      setFacturas(fac.data);
      setClientes(cli.data.filter((t) => t.tipo !== "proveedor"));
      setResoluciones(res.data);
      setProductos(pro.data);
      setFormasPago(fp.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Factura anulada: se revirtieron su asiento y su salida de inventario");
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
    setClienteId(doc?.cliente_id || "");
    setResolucionId(doc?.resolucion_id || (resoluciones.length === 1 ? resoluciones[0].id : ""));
    setFormaPagoId(doc?.forma_pago_id || "");
    setFecha(doc && m === "editar" ? doc.fecha : hoy());
    setVencimiento(doc && m === "editar" ? doc.fecha_vencimiento || "" : "");
    setObservaciones(doc?.observaciones || "");
    setLineas(
      doc
        ? doc.items.map((it) => ({
            producto_id: it.producto_id,
            cantidad: it.cantidad,
            precio_unitario: it.precio_unitario,
            tarifa_iva: it.tarifa_iva,
          }))
        : [lineaVentaVacia()]
    );
  };

  const guardar = async () => {
    setError(null);
    if (!clienteId) return setError("Selecciona un cliente");
    if (!resolucionId) return setError("Selecciona una resolución DIAN");
    if (lineas.some((l) => !l.producto_id)) return setError("Todas las líneas deben tener un producto");
    if (lineas.some((l) => Number(l.cantidad) <= 0)) return setError("Las cantidades deben ser mayores a cero");

    const cuerpo = {
      cliente_id: clienteId,
      resolucion_id: resolucionId,
      fecha,
      fecha_vencimiento: vencimiento || null,
      forma_pago_id: formaPagoId || null,
      items: lineas.map((l) => ({
        producto_id: l.producto_id,
        cantidad: Number(l.cantidad),
        precio_unitario: Number(l.precio_unitario),
        tarifa_iva: Number(l.tarifa_iva),
      })),
      observaciones: observaciones || null,
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/facturacion/facturas/${origen.id}`, cuerpo)
          : await api.post("/api/facturacion/facturas", cuerpo);
      setMensaje(`Factura ${numeroDoc(data)} ${modo === "editar" ? "actualizada" : "creada"} — Total ${fmtCOP(data.total)}`);
      setModo(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  };

  const enviarDian = async (id) => {
    setError(null);
    try {
      await api.post(`/api/facturacion/facturas/${id}/enviar-dian`);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const columnas = [
    { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
    { key: "fecha", label: "Fecha" },
    { key: "cliente_nombre", label: "Cliente" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    {
      key: "total_retenciones",
      label: "Retenciones",
      render: (r) => (r.total_retenciones ? `-${fmtCOP(r.total_retenciones)}` : r.autorretencion ? `Autorret. ${fmtCOP(r.autorretencion)}` : "—"),
    },
    { key: "saldo_pendiente", label: "Saldo", render: (r) => (r.estado === "anulado" ? "" : fmtCOP(r.saldo_pendiente)) },
    {
      key: "estado",
      label: "Estado",
      render: (r) => <EstadoBadge estado={r.estado === "anulado" ? "anulado" : r.estado_dian === "borrador" ? "sin enviar a la DIAN" : r.estado_dian} />,
    },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <div className="flex gap-3 items-center">
          <AccionesDocumento
            tipoDoc="factura"
            doc={r}
            modulo="facturacion"
            onEditar={(d) => abrir("editar", d)}
            onDuplicar={(d) => abrir("duplicar", d)}
            onAnular={(d) => anulacion.pedir(d, `/api/facturacion/facturas/${d.id}/anular`)}
            bloqueo={r.estado_dian && r.estado_dian !== "borrador" ? "Enviada a la DIAN: corrígela con una nota crédito" : null}
          />
          {puede("facturacion", "editar") && r.estado !== "anulado" && r.estado_dian === "borrador" && (
            <button onClick={() => enviarDian(r.id)} className="text-xs text-slate-500 hover:underline">
              Enviar DIAN
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Facturas de venta</h1>
        {puede("facturacion", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nueva factura
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-1">{tituloModo(modo, "factura", origen)}</h2>
          <p className="text-xs text-slate-500 mb-4">
            {modo === "editar"
              ? "Conserva su número. Los productos vendidos se descuentan de la bodega principal."
              : "El número lo asigna la resolución DIAN al guardar. Las retenciones que te practique el cliente se calculan solas según los perfiles tributarios."}
          </p>
          {resoluciones.length === 0 && (
            <p className="mb-3 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
              Primero registra una resolución DIAN en Configuración › Resoluciones DIAN.
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-2">
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
              <Select value={resolucionId} disabled={modo === "editar"} onChange={(e) => setResolucionId(e.target.value)}>
                <option value="">Seleccionar…</option>
                {resoluciones.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.prefijo} — Res. {r.numero_resolucion}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Fecha">
              <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </FormField>
            <FormField label="Vence">
              <Input type="date" value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} />
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

          <LineasVenta lineas={lineas} setLineas={setLineas} productos={productos} totales={totales} cobraIva={perfil?.cobra_iva !== false} />

          <FormField label="Observaciones">
            <Input value={observaciones} onChange={(e) => setObservaciones(e.target.value)} />
          </FormField>
          <div className="flex gap-2 mt-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Guardar factura"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300 hover:bg-slate-50">
              Cancelar
            </button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={facturas} empty="No hay facturas registradas" />
      {anulacion.modal}
    </div>
  );
}
