import { useEffect, useRef, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Avisos, SelectorCuenta, fmtCOP, mensajeError } from "../../../shared/documentos/index.jsx";

const EVENTOS = [
  ["030", "Acuse de recibo"],
  ["032", "Recibo del bien o servicio"],
  ["033", "Aceptación expresa"],
  ["031", "Reclamo"],
];
const MOTIVOS = { "01": "Documento con inconsistencias", "02": "Mercancía no entregada totalmente", "03": "Mercancía no entregada parcialmente", "04": "Servicio no prestado" };
const COLOR = { pendiente: "bg-slate-100 text-slate-600", acusada: "bg-sky-50 text-sky-700", "bien recibido": "bg-sky-50 text-sky-700", aceptada: "bg-emerald-50 text-emerald-700", reclamada: "bg-red-50 text-red-700" };

function EstadoRadian({ estado }) {
  return <span className={`inline-block text-[11px] rounded-sm px-1.5 py-0.5 ${COLOR[estado] || COLOR.pendiente}`}>{estado}</span>;
}

export default function Page() {
  const { puede } = useAuth();
  const entrada = useRef(null);
  const [lista, setLista] = useState([]);
  const [previa, setPrevia] = useState(null); // { archivo, factura, avisos }
  const [detalle, setDetalle] = useState(null);
  const [conta, setConta] = useState(null);
  const [cuentas, setCuentas] = useState([]);
  const [productos, setProductos] = useState([]);
  const [error, setError] = useState(null);
  const [errorModal, setErrorModal] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [motivo, setMotivo] = useState("01");
  const [obs, setObs] = useState("");

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/compras/facturas-recibidas");
      setLista(data);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => {
    cargar();
    api.get("/api/configuracion/plan-cuentas").then((r) => setCuentas(r.data)).catch(() => {});
    api.get("/api/inventario/catalogo-productos").then((r) => setProductos(r.data)).catch(() => {});
  }, []);

  const elegirArchivo = async (e) => {
    const archivo = e.target.files[0];
    e.target.value = "";
    if (!archivo) return;
    setError(null);
    setMensaje(null);
    const form = new FormData();
    form.append("archivo", archivo);
    try {
      const { data } = await api.post("/api/compras/facturas-recibidas", form, { params: { simular: true } });
      setPrevia({ archivo, factura: data.factura, avisos: data.avisos });
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const guardarPrevia = async () => {
    const form = new FormData();
    form.append("archivo", previa.archivo);
    try {
      const { data } = await api.post("/api/compras/facturas-recibidas", form);
      setMensaje(`Factura ${data.factura.numero_factura} cargada como ${data.factura.numero}`);
      setPrevia(null);
      cargar();
    } catch (err) {
      setErrorModal(mensajeError(err));
    }
  };

  const abrir = async (id) => {
    setErrorModal(null);
    const { data } = await api.get(`/api/compras/facturas-recibidas/${id}`);
    setDetalle(data);
  };

  const evento = async (codigo) => {
    setErrorModal(null);
    try {
      const { data } = await api.post(`/api/compras/facturas-recibidas/${detalle.id}/eventos`, {
        codigo, motivo: codigo === "031" ? motivo : null, observaciones: obs || null,
      });
      setDetalle(data);
      setObs("");
      cargar();
    } catch (err) {
      setErrorModal(mensajeError(err));
    }
  };

  const abrirConta = () => {
    setErrorModal(null);
    setConta({ afecta_inventario: false, cuenta_gasto: "", aplicar_reteiva: true, productos: {} });
  };

  const contabilizar = async () => {
    setErrorModal(null);
    try {
      const productosSel = Object.fromEntries(Object.entries(conta.productos).filter(([, v]) => v));
      const { data } = await api.post(`/api/compras/facturas-recibidas/${detalle.id}/contabilizar`, {
        afecta_inventario: conta.afecta_inventario, cuenta_gasto: conta.cuenta_gasto || null,
        aplicar_reteiva: conta.aplicar_reteiva, productos: productosSel,
      });
      setMensaje(`Contabilizada como ${data.numero} por ${fmtCOP(data.total)}`);
      setConta(null);
      setDetalle(null);
      cargar();
    } catch (err) {
      setErrorModal(mensajeError(err));
    }
  };

  const registrados = new Set((detalle?.eventos || []).map((e) => e.codigo));

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Facturas electrónicas recibidas</h1>
        {puede("compras", "crear") && (
          <>
            <input ref={entrada} type="file" accept=".xml" className="hidden" onChange={elegirArchivo} />
            <button onClick={() => entrada.current?.click()} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">
              Cargar XML
            </button>
          </>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-4">
        Carga el XML (o el AttachedDocument) que te envía el proveedor: se lee la factura, se registran los eventos de aceptación (RADIAN) y se contabiliza como factura de proveedor. Los eventos quedan pendientes de transmitir a la DIAN.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      <Table
        titulo="Facturas electrónicas recibidas"
        columns={[
          { key: "numero", label: "Interno", render: (r) => <b>{r.numero}</b> },
          { key: "numero_factura", label: "Factura" },
          { key: "fecha", label: "Fecha" },
          { key: "proveedor_nombre", label: "Proveedor" },
          { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
          { key: "estado_radian", label: "RADIAN", render: (r) => <EstadoRadian estado={r.estado_radian} /> },
          { key: "contabilizada", label: "Contabilizada", render: (r) => (r.contabilizada ? "Sí" : "No") },
          { key: "_acc", label: "", render: (r) => <button onClick={() => abrir(r.id)} className="text-xs text-geifem-blue hover:underline">Ver / gestionar</button> },
        ]}
        rows={lista}
        empty="Aún no cargas facturas electrónicas"
      />

      <Modal
        open={Boolean(previa)} onClose={() => setPrevia(null)} title="Revisa la factura antes de guardarla" ancho="max-w-3xl"
        footer={<>
          <button onClick={() => setPrevia(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={guardarPrevia} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Guardar</button>
        </>}
      >
        {previa && (
          <>
            {previa.avisos.map((a, i) => <p key={i} className="text-sm text-amber-700 mb-1">{a}</p>)}
            <p className="text-sm mt-2"><b>{previa.factura.numero_factura}</b> · {previa.factura.fecha} · vence {previa.factura.fecha_vencimiento || "—"}</p>
            <p className="text-sm text-slate-600 mb-2">{previa.factura.proveedor.nombre} (NIT {previa.factura.proveedor.nit}{previa.factura.proveedor.dv ? `-${previa.factura.proveedor.dv}` : ""})</p>
            <p className="text-xs text-slate-500 break-all mb-2">CUFE {previa.factura.cufe}</p>
            <Table titulo="Líneas de la factura" exportar={false} porPagina={10}
              columns={[{ key: "descripcion", label: "Descripción" }, { key: "cantidad", label: "Cant." }, { key: "costo_unitario", label: "Valor unit.", render: (r) => fmtCOP(r.costo_unitario) },
                { key: "tarifa_iva", label: "IVA %" }, { key: "subtotal", label: "Subtotal", render: (r) => fmtCOP(r.subtotal) }]}
              rows={previa.factura.items.map((it, i) => ({ ...it, id: i }))} />
            <p className="text-right text-sm mt-2">Total {fmtCOP(previa.factura.total_xml)}</p>
            {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
          </>
        )}
      </Modal>

      <Modal
        open={Boolean(detalle) && !conta} onClose={() => setDetalle(null)} title={detalle ? `${detalle.numero} · ${detalle.numero_factura}` : ""} ancho="max-w-3xl"
        footer={detalle && !detalle.contabilizada && puede("compras", "crear") && detalle.estado_radian !== "reclamada" ? (
          <button onClick={abrirConta} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Contabilizar como factura de proveedor</button>
        ) : null}
      >
        {detalle && (
          <>
            <p className="text-sm">{detalle.proveedor_nombre} · {fmtCOP(detalle.total)} · <EstadoRadian estado={detalle.estado_radian} /></p>
            <p className="text-xs text-slate-500 break-all mb-3">CUFE {detalle.cufe}</p>
            <h4 className="text-sm font-semibold mb-1">Eventos RADIAN</h4>
            {detalle.eventos.length === 0 && <p className="text-sm text-slate-500 mb-2">Sin eventos registrados.</p>}
            <ul className="text-sm mb-3">
              {detalle.eventos.map((e) => (
                <li key={e.codigo} className="border-b border-slate-100 py-1">
                  <b>{e.codigo}</b> {e.nombre} · {e.fecha}{e.motivo_nombre ? ` · ${e.motivo_nombre}` : ""}{e.observaciones ? ` · ${e.observaciones}` : ""}
                  <span className="ml-2 text-xs text-amber-700">transmisión {e.transmision}</span>
                </li>
              ))}
            </ul>
            {puede("compras", "editar") && (
              <>
                <div className="grid gap-2 sm:grid-cols-2">
                  <FormField label="Motivo del reclamo"><Select value={motivo} onChange={(e) => setMotivo(e.target.value)}>{Object.entries(MOTIVOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></FormField>
                  <FormField label="Observaciones"><Input value={obs} onChange={(e) => setObs(e.target.value)} /></FormField>
                </div>
                <div className="flex flex-wrap gap-2">
                  {EVENTOS.filter(([c]) => !registrados.has(c)).map(([c, n]) => (
                    <button key={c} onClick={() => evento(c)} className="text-xs px-3 py-1.5 rounded-sm border border-geifem-navy text-geifem-navy">Registrar {c} · {n}</button>
                  ))}
                </div>
              </>
            )}
            {errorModal && <p className="text-sm text-red-600 mt-2">{errorModal}</p>}
          </>
        )}
      </Modal>

      <Modal
        open={Boolean(conta)} onClose={() => setConta(null)} title="Contabilizar factura de proveedor" ancho="max-w-3xl"
        footer={<>
          <button onClick={() => setConta(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={contabilizar} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Contabilizar</button>
        </>}
      >
        {conta && detalle && (
          <>
            <label className="flex items-center gap-2 text-sm mb-2">
              <input type="checkbox" checked={conta.afecta_inventario} onChange={(e) => setConta({ ...conta, afecta_inventario: e.target.checked })} />
              Es mercancía (cruza contra la entrada de mercancía por facturar)
            </label>
            {!conta.afecta_inventario && (
              <FormField label="Cuenta de gasto o costo" hint="Vacía = la de los parámetros contables (compras)">
                <SelectorCuenta cuentas={cuentas} porCodigo value={conta.cuenta_gasto} onChange={(v) => setConta({ ...conta, cuenta_gasto: v })} />
              </FormField>
            )}
            <label className="flex items-center gap-2 text-sm mb-3">
              <input type="checkbox" checked={conta.aplicar_reteiva} onChange={(e) => setConta({ ...conta, aplicar_reteiva: e.target.checked })} />
              Aplicar ReteIVA cuando corresponda
            </label>
            {conta.afecta_inventario && (
              <>
                <h4 className="text-sm font-semibold mb-1">Producto de cada línea</h4>
                {detalle.items.map((it, i) => (
                  <div key={i} className="grid grid-cols-2 gap-2 mb-1 items-center text-sm">
                    <span>{it.descripcion} × {it.cantidad}</span>
                    <Select value={conta.productos[i] || ""} onChange={(e) => setConta({ ...conta, productos: { ...conta.productos, [i]: e.target.value } })}>
                      <option value="">Sin producto</option>
                      {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </Select>
                  </div>
                ))}
              </>
            )}
            <p className="text-xs text-slate-500 mt-2">Las retenciones se calculan solas según tu perfil tributario y el del proveedor. Si el proveedor no existe en terceros, se crea.</p>
            {errorModal && <p className="text-sm text-red-600 mt-2">{errorModal}</p>}
          </>
        )}
      </Modal>
    </div>
  );
}
