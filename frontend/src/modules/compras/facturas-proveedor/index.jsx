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
  SelectorCuenta,
  fmtCOP,
  hoy,
  mensajeError,
  numeroDoc,
  tituloModo,
  useAnulacion,
} from "../../../shared/documentos/index.jsx";
import LineasCompra, { itemsAFormulario, lineaCompraVacia, totalesCompra } from "../_LineasCompra.jsx";

const FORM_VACIO = () => ({
  proveedor_id: "",
  numero_factura: "",
  fecha: hoy(),
  fecha_vencimiento: "",
  orden_compra_id: "",
  afecta_inventario: true,
  cuenta_gasto: "",
  concepto_reteica_id: "",
  aplicar_reteiva: true,
  observaciones: "",
});

export default function Page() {
  const { puede } = useAuth();
  const { perfil } = useEmpresa();
  const [conceptos, setConceptos] = useState([]);
  const [calculo, setCalculo] = useState(null);
  const [facturas, setFacturas] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [productos, setProductos] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [form, setForm] = useState(FORM_VACIO());
  const [lineas, setLineas] = useState([lineaCompraVacia()]);

  const cargar = async () => {
    try {
      const [fp, te, pr, oc, pc, cr] = await Promise.all([
        api.get("/api/compras/facturas-proveedor"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/inventario/catalogo-productos"),
        api.get("/api/compras/ordenes-compra"),
        api.get("/api/configuracion/plan-cuentas"),
        api.get("/api/configuracion/conceptos-retencion"),
      ]);
      setConceptos(cr.data);
      setFacturas(fp.data);
      setProveedores(te.data.filter((t) => t.tipo !== "cliente"));
      setProductos(pr.data);
      setOrdenes(oc.data.filter((o) => o.estado !== "anulado"));
      setCuentas(pc.data.filter((c) => c.codigo.startsWith("5") || c.codigo.startsWith("6")));
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Factura de proveedor anulada");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const totales = useMemo(() => totalesCompra(lineas), [lineas]);

  const cuerpoDocumento = () => ({
    ...form,
    orden_compra_id: form.orden_compra_id || null,
    cuenta_gasto: form.cuenta_gasto || null,
    concepto_reteica_id: form.concepto_reteica_id || null,
    fecha_vencimiento: form.fecha_vencimiento || null,
    observaciones: form.observaciones || null,
    items: lineas.map((l) => ({
      producto_id: l.producto_id || null,
      descripcion: l.descripcion,
      cantidad: Number(l.cantidad),
      costo_unitario: Number(l.costo_unitario),
      tarifa_iva: Number(l.tarifa_iva),
      concepto_retefuente_id: l.concepto_retefuente_id || null,
    })),
  });

  // Las retenciones las calcula el servidor con los perfiles tributarios; se previsualizan en vivo.
  useEffect(() => {
    if (!modo || !form.proveedor_id) {
      setCalculo(null);
      return undefined;
    }
    const t = setTimeout(() => {
      api
        .post("/api/compras/facturas-proveedor/previsualizar", cuerpoDocumento())
        .then((r) => setCalculo(r.data))
        .catch(() => setCalculo(null));
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo, form, lineas]);

  const set = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    if (doc) {
      setForm({
        ...FORM_VACIO(),
        proveedor_id: doc.proveedor_id,
        numero_factura: m === "editar" ? doc.numero_factura : "",
        fecha: m === "editar" ? doc.fecha : hoy(),
        fecha_vencimiento: m === "editar" ? doc.fecha_vencimiento || "" : "",
        orden_compra_id: m === "editar" ? doc.orden_compra_id || "" : "",
        afecta_inventario: doc.afecta_inventario,
        cuenta_gasto: doc.cuenta_gasto || "",
        concepto_reteica_id: doc.concepto_reteica_id || "",
        aplicar_reteiva: doc.aplicar_reteiva ?? true,
        observaciones: doc.observaciones || "",
      });
      setLineas(itemsAFormulario(doc.items));
    } else {
      setForm(FORM_VACIO());
      setLineas([lineaCompraVacia()]);
    }
  };

  const cargarDesdeOrden = (id) => {
    const oc = ordenes.find((o) => o.id === id);
    setForm((f) => ({ ...f, orden_compra_id: id, proveedor_id: oc?.proveedor_id || f.proveedor_id }));
    if (oc?.items?.length) setLineas(itemsAFormulario(oc.items));
  };

  const guardar = async () => {
    setError(null);
    if (!form.proveedor_id) return setError("Selecciona el proveedor");
    if (!form.numero_factura.trim()) return setError("Escribe el número de la factura del proveedor");
    if (lineas.some((l) => !l.producto_id && !l.descripcion.trim())) return setError("Cada línea necesita producto o descripción");
    const cuerpo = cuerpoDocumento();
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/compras/facturas-proveedor/${origen.id}`, cuerpo)
          : await api.post("/api/compras/facturas-proveedor", cuerpo);
      setMensaje(`${numeroDoc(data)} (factura ${data.numero_factura}) ${modo === "editar" ? "actualizada" : "registrada"} — neto a pagar ${fmtCOP(data.total_a_pagar)}`);
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
    { key: "numero_factura", label: "Factura proveedor" },
    { key: "fecha", label: "Fecha" },
    { key: "proveedor_nombre", label: "Proveedor" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "total_retenciones", label: "Retenciones", render: (r) => fmtCOP(r.total_retenciones) },
    { key: "saldo_pendiente", label: "Saldo", render: (r) => (r.estado === "anulado" ? "" : fmtCOP(r.saldo_pendiente)) },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="factura_proveedor"
          doc={r}
          modulo="compras"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/compras/facturas-proveedor/${d.id}/anular`)}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Facturas de proveedor</h1>
        {puede("compras", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nueva factura
          </button>
        )}
      </div>
      <p className="text-slate-500 text-sm mb-4">
        Contabiliza la compra o el gasto, el IVA descontable, las retenciones y la cuenta por pagar.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-3">{tituloModo(modo, "factura de proveedor", origen)}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <FormField label="Orden de compra (opcional)">
              <Select value={form.orden_compra_id} onChange={(e) => cargarDesdeOrden(e.target.value)}>
                <option value="">Sin orden</option>
                {ordenes.map((o) => (
                  <option key={o.id} value={o.id}>{numeroDoc(o)} · {o.proveedor_nombre}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Proveedor">
              <Select value={form.proveedor_id} onChange={set("proveedor_id")}>
                <option value="">Seleccionar…</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="N° factura del proveedor">
              <Input value={form.numero_factura} onChange={set("numero_factura")} />
            </FormField>
            <FormField label="Fecha">
              <Input type="date" value={form.fecha} onChange={set("fecha")} />
            </FormField>
            <FormField label="Vence">
              <Input type="date" value={form.fecha_vencimiento} onChange={set("fecha_vencimiento")} />
            </FormField>
          </div>

          <div className="flex flex-wrap items-center gap-4 mb-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={form.afecta_inventario} onChange={set("afecta_inventario")} />
              Es compra de mercancía (cruza lo registrado con la entrada de mercancía)
            </label>
            {!form.afecta_inventario && (
              <div className="w-80">
                <SelectorCuenta cuentas={cuentas} porCodigo vacio="Usar la de Parámetros contables" value={form.cuenta_gasto}
                  onChange={(v) => setForm((f) => ({ ...f, cuenta_gasto: v }))} />
              </div>
            )}
          </div>

          {perfil && perfil.cobra_iva === false && (
            <p className="mb-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
              Tu empresa no es responsable de IVA: el IVA de esta factura se suma al costo o gasto (no es descontable).
            </p>
          )}
          <LineasCompra lineas={lineas} setLineas={setLineas} productos={productos}
            conceptos={perfil?.practica_retefuente ? conceptos.filter((c) => c.tipo === "retefuente") : null} />

          {perfil && (perfil.practica_reteica || perfil.practica_reteiva) && (
            <div className="grid gap-3 sm:grid-cols-2 items-end">
              {perfil.practica_reteica && (
                <FormField label="ReteICA">
                  <Select value={form.concepto_reteica_id} onChange={set("concepto_reteica_id")}>
                    <option value="">No aplica</option>
                    {conceptos.filter((c) => c.tipo === "reteica").map((c) => (
                      <option key={c.id} value={c.id}>{c.nombre} ({c.tarifa}‰)</option>
                    ))}
                  </Select>
                </FormField>
              )}
              {perfil.practica_reteiva && (
                <label className="flex items-center gap-2 text-sm text-slate-700 pb-3">
                  <input type="checkbox" checked={form.aplicar_reteiva} onChange={set("aplicar_reteiva")} />
                  Practicar ReteIVA (15% del IVA) si el proveedor es responsable de IVA
                </label>
              )}
            </div>
          )}
          {perfil && !perfil.practica_retefuente && perfil.notas?.length > 0 && (
            <p className="mb-2 text-xs text-slate-500">{perfil.notas[0]}</p>
          )}

          {calculo && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3 text-sm">
              <div className="flex flex-wrap gap-x-6 gap-y-1 justify-end">
                <span>ReteFuente <b>-{fmtCOP(calculo.retenciones.retefuente)}</b></span>
                <span>ReteICA <b>-{fmtCOP(calculo.retenciones.reteica)}</b></span>
                <span>ReteIVA <b>-{fmtCOP(calculo.retenciones.reteiva)}</b></span>
                <span className="text-geifem-navy">Neto a pagar <b>{fmtCOP(calculo.total_a_pagar)}</b></span>
              </div>
              {calculo.detalle_retenciones.filter((d) => !d.aplica).map((d, i) => (
                <p key={i} className="text-xs text-slate-500 text-right">{d.concepto}: {d.motivo}</p>
              ))}
            </div>
          )}
          <FormField label="Observaciones">
            <Input value={form.observaciones} onChange={set("observaciones")} />
          </FormField>
          <div className="flex gap-2">
            <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
              {guardando ? "Guardando…" : modo === "editar" ? "Guardar cambios" : "Registrar factura"}
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={facturas} empty="No hay facturas de proveedor" />
      {anulacion.modal}
    </div>
  );
}
