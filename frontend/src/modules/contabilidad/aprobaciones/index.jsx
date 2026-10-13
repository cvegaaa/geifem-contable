import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, fmtCOP, mensajeError } from "../../../shared/documentos/index.jsx";

const ESTADOS = { pendiente: "Pendientes", aprobada: "Aprobadas", rechazada: "Rechazadas", cancelada: "Retiradas", todas: "Todas" };
const COLOR = {
  pendiente: "bg-amber-50 text-amber-700", aprobada: "bg-emerald-50 text-emerald-700",
  rechazada: "bg-red-50 text-red-700", cancelada: "bg-slate-100 text-slate-600",
};
const MODULOS = { facturacion: "Facturación", compras: "Compras", tesoreria: "Tesorería", inventario: "Inventario", nomina: "Nómina", contabilidad: "Contabilidad" };
const ETIQUETA_RESUMEN = {
  fecha: "Fecha", valor: "Valor", total: "Total", motivo: "Motivo", numero_factura: "Factura del proveedor", concepto: "Concepto",
  observaciones: "Observaciones", tipo: "Tipo", documento_tipo: "Documento", "líneas": "Líneas", subtotal_estimado: "Subtotal estimado",
  facturas: "Facturas", descripcion: "Descripción",
};

export default function Page() {
  const [estado, setEstado] = useState("pendiente");
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [rechazo, setRechazo] = useState(null);
  const [motivo, setMotivo] = useState("");

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/aprobaciones", { params: { estado } });
      setItems(data);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [estado]);

  const ruta = (i, accion) => (i.tipo === "comprobante" ? `/api/contabilidad/comprobantes/${i.id}/${accion}` : `/api/aprobaciones/${i.id}/${accion}`);
  const avisarCambio = () => window.dispatchEvent(new CustomEvent("aprobaciones:cambio"));

  const aprobar = async (i) => {
    setError(null); setMensaje(null);
    try {
      const { data } = await api.post(ruta(i, "aprobar"));
      setMensaje(`${i.descripcion}: aprobado${data?.resultado?.numero ? ` — quedó registrado como ${data.resultado.numero}` : ""}`);
      cargar(); avisarCambio();
    } catch (e) {
      setError(mensajeError(e));
      cargar();
    }
  };

  const rechazar = async () => {
    setError(null);
    try {
      await api.post(ruta(rechazo, "rechazar"), { motivo });
      setMensaje(`${rechazo.descripcion}: rechazado`);
      setRechazo(null); setMotivo("");
      cargar(); avisarCambio();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  const retirar = async (i) => {
    try {
      await api.post(`/api/aprobaciones/${i.id}/cancelar`);
      setMensaje("Solicitud retirada");
      cargar(); avisarCambio();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Aprobaciones</h1>
      <p className="text-sm text-slate-500 mb-4">
        Los documentos de los usuarios que requieren aprobación (ventas, compras, tesorería, inventario, nómina y comprobantes) no se registran hasta que un aprobador los autoriza.
        Al aprobar, el documento queda a nombre de quien lo solicitó y con tu nombre como aprobador.
      </p>
      <Avisos error={error} mensaje={mensaje} />
      <div className="flex gap-2 mb-3 flex-wrap">
        {Object.entries(ESTADOS).map(([k, v]) => (
          <button key={k} onClick={() => setEstado(k)}
            className={`text-xs border rounded-sm px-2 py-1 ${estado === k ? "border-geifem-navy bg-geifem-navy text-white" : "border-slate-300"}`}>{v}</button>
        ))}
      </div>
      <Table
        titulo="Aprobaciones"
        columns={[
          { key: "creado_en", label: "Solicitada", render: (r) => (r.creado_en ? new Date(r.creado_en).toLocaleString("es-CO") : "") },
          { key: "descripcion", label: "Documento", render: (r) => <b>{r.descripcion}</b> },
          { key: "modulo", label: "Módulo", render: (r) => MODULOS[r.modulo] || r.modulo },
          { key: "usuario_nombre", label: "Solicitó" },
          {
            key: "resumen", label: "Detalle",
            render: (r) => (
              <div className="text-xs text-slate-600">
                {Object.entries(r.resumen || {}).map(([k, v]) => (
                  <div key={k}>{ETIQUETA_RESUMEN[k] || k}: {["valor", "total", "subtotal_estimado"].includes(k) ? fmtCOP(v) : String(v)}</div>
                ))}
                {r.ultimo_error && <div className="text-red-600">Último intento: {r.ultimo_error}</div>}
                {r.motivo_rechazo && <div className="text-red-600">Motivo: {r.motivo_rechazo}</div>}
                {r.resultado?.numero && <div className="text-emerald-700">Registrado: {r.resultado.numero}{r.aprobado_por ? ` · aprobó ${r.aprobado_por}` : ""}</div>}
              </div>
            ),
          },
          { key: "estado", label: "Estado", render: (r) => <span className={`text-[11px] rounded-sm px-1.5 py-0.5 ${COLOR[r.estado] || COLOR.pendiente}`}>{r.estado}</span> },
          {
            key: "_acc", label: "",
            render: (r) => (
              <div className="flex gap-3 whitespace-nowrap">
                {r.puede_resolver && <button onClick={() => aprobar(r)} className="text-xs text-emerald-700 hover:underline">Aprobar</button>}
                {r.puede_resolver && <button onClick={() => { setRechazo(r); setMotivo(""); }} className="text-xs text-red-600 hover:underline">Rechazar</button>}
                {r.propio && r.estado === "pendiente" && r.tipo === "solicitud" && <button onClick={() => retirar(r)} className="text-xs text-slate-600 hover:underline">Retirar</button>}
              </div>
            ),
          },
        ]}
        rows={items}
        empty="No hay solicitudes en este estado"
      />

      <Modal
        open={Boolean(rechazo)} onClose={() => setRechazo(null)} title={rechazo ? `Rechazar: ${rechazo.descripcion}` : ""}
        footer={<>
          <button onClick={() => setRechazo(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={rechazar} className="px-4 py-1.5 text-sm rounded-sm bg-red-600 text-white">Rechazar</button>
        </>}
      >
        <p className="text-sm text-slate-600 mb-2">La solicitud no se registra; quien la hizo verá tu motivo.</p>
        <FormField label="Motivo"><Input value={motivo} onChange={(e) => setMotivo(e.target.value)} /></FormField>
      </Modal>
    </div>
  );
}
