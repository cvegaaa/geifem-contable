import { createContext, useContext, useEffect, useState } from "react";
import api from "../../core/api.js";
import { useEmpresa } from "../../core/EmpresaContext.jsx";
import Modal from "../layout/Modal/index.jsx";
import { fmtCOP, numeroDoc } from "./index.jsx";

const VistaContext = createContext({ abrir: () => {} });

export const useVistaDocumento = () => useContext(VistaContext);

const NOMBRES = {
  factura: "Factura de venta",
  pos: "Documento equivalente POS",
  nota: "Nota",
  orden_compra: "Orden de compra",
  entrada: "Entrada de mercancía",
  factura_proveedor: "Factura de proveedor",
  pago: "Pago",
  movimiento: "Movimiento de tesorería",
  comprobante: "Comprobante contable",
};

const cols = {
  venta: [["descripcion", "Descripción"], ["cantidad", "Cant."], ["precio_unitario", "Valor unit.", true], ["tarifa_iva", "IVA %"], ["total", "Total", true]],
  compra: [["descripcion", "Descripción"], ["cantidad", "Cant."], ["costo_unitario", "Costo unit.", true], ["tarifa_iva", "IVA %"], ["total", "Total", true]],
  entrada: [["producto_nombre", "Producto"], ["cantidad", "Cant."], ["costo_unitario", "Costo unit.", true], ["valor", "Valor", true]],
};

/** Convierte cualquier documento a una estructura común para imprimirlo. */
function normalizar(tipo, d, cuentas) {
  const base = { numero: numeroDoc(d), fecha: d.fecha, estado: d.estado, observaciones: d.observaciones };
  const t = (label, valor, negativo = false, fuerte = false) => (valor || valor === 0 ? { label, valor, negativo, fuerte } : null);
  if (tipo === "factura" || tipo === "pos") {
    return {
      ...base, titulo: NOMBRES[tipo], tercero: ["Cliente", d.cliente_nombre], items: d.items, columnas: cols.venta,
      datos: [["Vence", d.fecha_vencimiento], ["Caja", d.caja_nombre], ["Estado DIAN", d.estado_dian], ["CUFE", d.cufe]],
      totales: [t("Subtotal", d.subtotal), t("IVA", d.iva_total), d.inc_total ? t("Impuesto al consumo", d.inc_total) : null,
        t("Total", d.total, false, true), d.total_retenciones ? t("Retenciones que te practican", d.total_retenciones, true) : null,
        d.total_retenciones ? t("Neto a cobrar", d.total_a_cobrar, false, true) : null, tipo === "factura" ? t("Saldo pendiente", d.saldo_pendiente) : null],
    };
  }
  if (tipo === "nota") {
    return {
      ...base, titulo: `Nota ${d.tipo === "credito" ? "crédito" : "débito"}`, tercero: ["Cliente", d.cliente_nombre], items: d.items,
      columnas: cols.venta, datos: [["Factura origen", d.factura_numero], ["Motivo", d.motivo]],
      totales: [t("Subtotal", d.subtotal), t("IVA", d.iva_total), d.inc_total ? t("Impuesto al consumo", d.inc_total) : null, t("Total", d.total, false, true),
        d.total_retenciones ? t("Retenciones trasladadas", d.total_retenciones, true) : null, d.neto != null ? t("Neto", d.neto, false, true) : null],
    };
  }
  if (tipo === "orden_compra") {
    return { ...base, titulo: NOMBRES[tipo], tercero: ["Proveedor", d.proveedor_nombre], items: d.items, columnas: cols.compra, datos: [],
      totales: [t("Subtotal", d.subtotal), t("IVA", d.iva_total), t("Total", d.total, false, true)] };
  }
  if (tipo === "entrada") {
    return { ...base, titulo: NOMBRES[tipo], tercero: ["Bodega", d.bodega_nombre], items: d.items, columnas: cols.entrada, datos: [],
      totales: [t("Valor total", d.valor_total, false, true)] };
  }
  if (tipo === "factura_proveedor") {
    const r = d.retenciones || {};
    return {
      ...base, titulo: NOMBRES[tipo], tercero: ["Proveedor", d.proveedor_nombre], items: d.items, columnas: cols.compra,
      datos: [["Factura del proveedor", d.numero_factura], ["Vence", d.fecha_vencimiento]],
      totales: [t("Subtotal", d.subtotal), t("IVA", d.iva_total), t("Total", d.total, false, true), r.retefuente ? t("ReteFuente", r.retefuente, true) : null,
        r.reteica ? t("ReteICA", r.reteica, true) : null, r.reteiva ? t("ReteIVA", r.reteiva, true) : null, t("Neto a pagar", d.total_a_pagar, false, true),
        t("Saldo pendiente", d.saldo_pendiente)],
    };
  }
  if (tipo === "pago") {
    return {
      ...base, titulo: d.documento_tipo === "cxc" ? "Recibo de caja" : "Comprobante de egreso", tercero: [d.documento_tipo === "cxc" ? "Recibido de" : "Pagado a", d.tercero_nombre],
      items: null, datos: [["Por concepto de", `${d.documento_tipo === "cxc" ? "Cobro" : "Pago"} de ${d.documento_numero}`], ["Medio", d.cuenta_nombre], ["Observaciones", d.observaciones]],
      totales: [t("Valor", d.valor, false, true), t("Saldo del documento", d.saldo_resultante)], firmas: true,
    };
  }
  if (tipo === "movimiento") {
    return { ...base, titulo: d.tipo === "ingreso" ? "Ingreso de tesorería" : "Egreso de tesorería", tercero: ["Cuenta", d.cuenta_nombre], items: null,
      datos: [["Concepto", d.concepto], ["Cuenta contable", d.cuenta_contable], ["Contrapartida", d.cuenta_contrapartida]],
      totales: [t("Valor", d.valor, false, true)], firmas: true };
  }
  // comprobante
  const nombre = (id) => {
    const c = cuentas.find((x) => x.id === id);
    return c ? `${c.codigo} — ${c.nombre}` : id;
  };
  return {
    ...base, titulo: `Comprobante de ${d.tipo}`, tercero: null, items: (d.lineas || []).map((l) => ({ ...l, cuenta: nombre(l.cuenta_puc_id) })),
    columnas: [["cuenta", "Cuenta"], ["descripcion", "Detalle"], ["debito", "Débito", true], ["credito", "Crédito", true]], datos: [["Descripción", d.descripcion]],
    totales: [t("Total débitos", (d.lineas || []).reduce((s, l) => s + Number(l.debito || 0), 0), false, true), t("Total créditos", (d.lineas || []).reduce((s, l) => s + Number(l.credito || 0), 0), false, true)],
    firmas: true,
  };
}

function Documento({ vista }) {
  const { empresaActiva } = useEmpresa();
  const [cuentas, setCuentas] = useState([]);
  useEffect(() => {
    if (vista.tipo === "comprobante") api.get("/api/configuracion/plan-cuentas").then((r) => setCuentas(r.data)).catch(() => {});
  }, [vista.tipo]);
  const n = normalizar(vista.tipo, vista.doc, cuentas);
  return (
    <div className="imprimible relative bg-white p-6 text-sm text-slate-800">
      {n.estado === "anulado" && (
        <div className="absolute inset-0 grid place-items-center pointer-events-none">
          <span className="text-6xl font-bold text-red-200 -rotate-12 border-8 border-red-200 px-6 py-2 rounded-lg">ANULADO</span>
        </div>
      )}
      <div className="flex justify-between border-b border-slate-300 pb-3 mb-3">
        <div>
          <div className="text-lg font-bold">{empresaActiva?.razon_social}</div>
          <div className="text-xs text-slate-500">
            NIT {empresaActiva?.nit}{empresaActiva?.dv ? `-${empresaActiva.dv}` : ""} · {empresaActiva?.regimen_tributario === "SIMPLE" ? "Régimen SIMPLE" : "Régimen ordinario"}
          </div>
          <div className="text-xs text-slate-500">{[empresaActiva?.direccion, empresaActiva?.ciudad, empresaActiva?.telefono].filter(Boolean).join(" · ")}</div>
        </div>
        <div className="text-right">
          <div className="font-semibold">{n.titulo}</div>
          <div className="text-lg font-bold text-geifem-navy">{n.numero}</div>
          <div className="text-xs text-slate-500">Fecha: {n.fecha}</div>
        </div>
      </div>
      {n.tercero && n.tercero[1] && (
        <div className="mb-2"><span className="text-slate-500">{n.tercero[0]}:</span> <b>{n.tercero[1]}</b></div>
      )}
      <div className="grid grid-cols-2 gap-x-6 mb-3">
        {n.datos.filter((x) => x[1]).map(([k, v]) => (
          <div key={k}><span className="text-slate-500">{k}:</span> {v}</div>
        ))}
      </div>
      {n.items && (
        <table className="w-full mb-3 text-xs">
          <thead>
            <tr className="border-y border-slate-300 bg-slate-50">
              {n.columnas.map(([k, l, dinero]) => (
                <th key={k} className={`px-2 py-1.5 ${dinero || k === "cantidad" || k === "tarifa_iva" ? "text-right" : "text-left"}`}>{l}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {n.items.map((it, i) => (
              <tr key={i} className="border-b border-slate-100">
                {n.columnas.map(([k, , dinero]) => (
                  <td key={k} className={`px-2 py-1 ${dinero || k === "cantidad" || k === "tarifa_iva" ? "text-right" : ""}`}>
                    {dinero ? (it[k] ? fmtCOP(it[k]) : "") : it[k] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="ml-auto w-72">
        {n.totales.filter(Boolean).map((x) => (
          <div key={x.label} className={`flex justify-between py-0.5 ${x.fuerte ? "font-bold border-t border-slate-300 mt-1 pt-1" : ""}`}>
            <span>{x.label}</span><span>{x.negativo ? "-" : ""}{fmtCOP(x.valor)}</span>
          </div>
        ))}
      </div>
      {n.observaciones && <p className="mt-3 text-xs text-slate-600"><b>Observaciones:</b> {n.observaciones}</p>}
      {n.firmas && (
        <div className="grid grid-cols-2 gap-12 mt-14 text-xs text-slate-500">
          <div className="border-t border-slate-400 pt-1 text-center">Elaboró</div>
          <div className="border-t border-slate-400 pt-1 text-center">Recibió / firma y sello</div>
        </div>
      )}
      {vista.doc.estado_dian && vista.doc.estado_dian !== "borrador" && vista.doc.cufe && (
        <p className="mt-3 text-[10px] break-all text-slate-400">CUFE: {vista.doc.cufe}</p>
      )}
    </div>
  );
}

/** Proveedor del visor: se coloca una sola vez en el layout. */
export function VistaDocumentoProvider({ children }) {
  const [vista, setVista] = useState(null);
  return (
    <VistaContext.Provider value={{ abrir: (doc, tipo) => setVista({ doc, tipo }) }}>
      {children}
      <Modal
        open={Boolean(vista)}
        onClose={() => setVista(null)}
        title={vista ? `${NOMBRES[vista.tipo]} ${numeroDoc(vista.doc)}` : ""}
        ancho="max-w-3xl"
        footer={
          <>
            <button onClick={() => setVista(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm no-imprimir">Cerrar</button>
            <button onClick={() => window.print()} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm no-imprimir">Imprimir / guardar PDF</button>
          </>
        }
      >
        {vista && <Documento vista={vista} />}
      </Modal>
    </VistaContext.Provider>
  );
}
