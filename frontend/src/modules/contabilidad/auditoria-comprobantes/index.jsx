import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

const TIPOS = [
  ["comprobante", "Comprobante contable"], ["factura", "Factura de venta"], ["pos", "Documento POS"], ["nota", "Nota crédito/débito"],
  ["orden_compra", "Orden de compra"], ["recepcion", "Entrada de mercancía"], ["factura_proveedor", "Factura de proveedor"],
  ["factura_recibida", "Factura electrónica recibida"], ["devolucion_proveedor", "Devolución a proveedor"],
  ["movimiento_tesoreria", "Movimiento de caja/banco"], ["pago", "Recibo / egreso"], ["anticipo", "Anticipo"],
  ["aplicacion_anticipo", "Aplicación de anticipo"], ["transferencia", "Transferencia"], ["ajuste_inventario", "Ajuste de inventario"],
  ["nomina_periodo", "Liquidación de nómina"], ["pago_nomina", "Pago de nómina"], ["pago_obligacion", "Pago de prestaciones / aportes"],
  ["nomina_liquidacion_final", "Liquidación de contrato"], ["cierre_periodo", "Cierre de periodo"],
];

const ACCIONES = ["creado", "editado", "anulado", "aprobado", "rechazado", "reabierto", "cerrado", "contabilizada", "cerrado"];

const COLOR = {
  creado: "bg-emerald-50 text-emerald-700", editado: "bg-sky-50 text-sky-700", anulado: "bg-red-50 text-red-700",
  aprobado: "bg-emerald-50 text-emerald-700", rechazado: "bg-red-50 text-red-700",
};

export default function Page() {
  const [rows, setRows] = useState([]);
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [tipo, setTipo] = useState("");
  const [accion, setAccion] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);

  const cargar = async () => {
    setError(null);
    try {
      const params = {};
      if (tipo) params.documento_tipo = tipo;
      if (accion) params.accion = accion;
      if (q.trim()) params.q = q.trim();
      if (rango.desde) params.desde = rango.desde;
      if (rango.hasta) params.hasta = rango.hasta;
      const { data } = await api.get("/api/contabilidad/auditoria", { params });
      setRows(data);
    } catch (e) {
      setRows([]);
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [tipo, accion]);

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Auditoría</h1>
      <p className="text-sm text-slate-500 mb-3">
        Historial de solo lectura: qué se hizo con cada documento (creación, edición, anulación, aprobación…), cuándo y quién. Últimos 500 eventos.
        Los documentos no se eliminan: se anulan y conservan su número.
      </p>
      <div className="flex flex-wrap gap-3 items-end mb-3">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Documento</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm bg-white">
            <option value="">Todos</option>
            {TIPOS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Acción</label>
          <select value={accion} onChange={(e) => setAccion(e.target.value)} className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm bg-white">
            <option value="">Todas</option>
            {[...new Set(ACCIONES)].map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Número</label>
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()}
            className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm" placeholder="CA-3, FE-10…" />
        </div>
        <button onClick={cargar} className="px-3 py-1.5 bg-geifem-navy text-white text-sm rounded-sm">Consultar</button>
      </div>
      <Avisos error={error} />
      <Table
        titulo="Auditoría"
        columns={[
          { key: "fecha_hora", label: "Fecha y hora", render: (r) => new Date(r.fecha_hora).toLocaleString("es-CO") },
          { key: "documento_nombre", label: "Tipo de documento" },
          { key: "numero", label: "Comprobante / número" },
          { key: "accion", label: "Acción", render: (r) => <span className={`capitalize text-xs px-1.5 py-0.5 rounded-sm ${COLOR[r.accion] || "bg-slate-100 text-slate-700"}`}>{r.accion}</span> },
          { key: "usuario_nombre", label: "Usuario", render: (r) => r.usuario_nombre || "—" },
          { key: "detalle", label: "Detalle", render: (r) => r.detalle?.motivo || r.detalle?.origen || "" },
        ]}
        rows={rows}
        empty="Sin eventos registrados"
      />
    </div>
  );
}
