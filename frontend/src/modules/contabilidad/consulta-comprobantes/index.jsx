import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";
import { Avisos, EstadoBadge, fmtCOP, mensajeError } from "../../../shared/documentos/index.jsx";
import { useVistaDocumento } from "../../../shared/documentos/Imprimible.jsx";

const PAGINA_POR_TIPO = {
  ajuste: "comprobante-ajuste",
  nota: "notas-contables",
  apertura: "comprobante-apertura",
  cierre: "comprobante-cierre",
};

const TIPOS = [
  ["", "Todos los documentos"],
  ["comprobante", "Comprobantes contables"],
  ["factura", "Facturas de venta"],
  ["pos", "Documentos POS"],
  ["nota", "Notas crédito/débito"],
  ["recepcion", "Entradas de mercancía"],
  ["factura_proveedor", "Facturas de proveedor"],
  ["devolucion_proveedor", "Devoluciones a proveedor"],
  ["pago", "Recibos de caja y egresos"],
  ["anticipo", "Anticipos"],
  ["aplicacion_anticipo", "Aplicaciones de anticipo"],
  ["movimiento_tesoreria", "Movimientos de caja y bancos"],
  ["transferencia", "Transferencias"],
  ["ajuste_inventario", "Ajustes de inventario"],
  ["ajuste_costo", "Ajustes de costo de venta"],
  ["nomina_periodo", "Liquidaciones de nómina"],
  ["pago_nomina", "Pagos de nómina"],
  ["pago_obligacion", "Pagos de prestaciones y aportes"],
  ["nomina_liquidacion_final", "Liquidaciones de contrato"],
];

export default function Page() {
  const navigate = useNavigate();
  const { abrir } = useVistaDocumento();
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [tipo, setTipo] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [auditoria, setAuditoria] = useState([]);

  const cargar = async () => {
    setError(null);
    try {
      const params = {};
      if (rango.desde) params.desde = rango.desde;
      if (rango.hasta) params.hasta = rango.hasta;
      if (tipo) params.tipo = tipo;
      if (q.trim()) params.q = q.trim();
      const { data } = await api.get("/api/contabilidad/documentos", { params });
      setRows(data.map((d) => ({ ...d, id: `${d.documento_tipo}:${d.documento_id}` })));
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, []);

  const verAsientos = async (r) => {
    setError(null);
    setAuditoria([]);
    try {
      const [det, aud] = await Promise.all([
        api.get(`/api/contabilidad/documentos/${r.documento_tipo}/${r.documento_id}/asientos`),
        api.get("/api/contabilidad/auditoria", { params: { documento_id: r.documento_id } }),
      ]);
      setDetalle({ ...det.data, estado: r.estado, documento_id: r.documento_id });
      setAuditoria(aud.data);
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  // Los comprobantes manuales se editan en su pantalla; los demás documentos, en su módulo.
  const abrirOrigen = async (r) => {
    if (r.documento_tipo === "comprobante") {
      try {
        const { data } = await api.get(`/api/contabilidad/comprobantes/${r.documento_id}`);
        navigate(`/contabilidad/${PAGINA_POR_TIPO[data.tipo]}?editar=${r.documento_id}`);
      } catch (e) {
        setError(mensajeError(e));
      }
    } else if (r.ruta) {
      navigate(r.ruta);
    }
  };

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Consulta de comprobantes</h1>
      <p className="text-sm text-slate-500 mb-4">
        Todos los documentos que llegaron a la contabilidad, de cualquier módulo: ventas, compras, cartera, tesorería, inventario y nómina.
        Cada uno tiene su comprobante contable con las cuentas y los terceros afectados.
      </p>
      <div className="flex gap-3 mb-3 items-end flex-wrap">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Documento</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm bg-white">
            {TIPOS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Número</label>
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()}
            placeholder="FE-12, RC-3…" className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm" />
        </div>
        <button onClick={cargar} className="px-3 py-1.5 bg-geifem-navy text-white text-sm rounded-sm">Consultar</button>
      </div>
      <Avisos error={error} />
      <Table
        titulo="Comprobantes contables"
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{r.numero}</span> },
          { key: "tipo_nombre", label: "Documento" },
          { key: "fecha", label: "Fecha" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acc", label: "",
            render: (r) => (
              <div className="flex gap-3 whitespace-nowrap">
                {r.estado === "contabilizado" && <button onClick={() => verAsientos(r)} className="text-xs text-geifem-blue hover:underline">Ver asientos</button>}
                {(r.ruta || r.documento_tipo === "comprobante") && (
                  <button onClick={() => abrirOrigen(r)} className="text-xs text-slate-600 hover:underline">
                    {r.documento_tipo === "comprobante" ? "Editar" : "Abrir en su módulo"}
                  </button>
                )}
              </div>
            ),
          },
        ]}
        rows={rows}
        empty="No hay documentos en el rango"
      />

      <Modal
        open={Boolean(detalle)} onClose={() => setDetalle(null)} ancho="max-w-4xl"
        title={detalle ? `${detalle.tipo_nombre} ${detalle.numero}` : ""}
        footer={detalle && (
          <>
            {detalle.ruta && <Link to={detalle.ruta} onClick={() => setDetalle(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Abrir en su módulo</Link>}
            <button onClick={() => { abrir({ ...detalle, numero: detalle.numero }, "asientos"); }} className="px-3 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Ver / imprimir comprobante</button>
          </>
        )}
      >
        {detalle && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
              <div><span className="text-slate-500">Fecha:</span> {detalle.fecha}</div>
              <div><span className="text-slate-500">Elaboró:</span> {detalle.elaboro || "—"}</div>
              <div><span className="text-slate-500">Aprobó:</span> {detalle.aprobo || "—"}</div>
            </div>
            <div className="border border-slate-200 rounded-sm overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="text-left px-3 py-2">Cuenta</th>
                    <th className="text-left px-3 py-2">Tercero</th>
                    <th className="text-right px-3 py-2 w-28">Débito</th>
                    <th className="text-right px-3 py-2 w-28">Crédito</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.lineas.map((l, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-1.5">{l.cuenta_codigo} — {l.cuenta_nombre}{l.descripcion && <div className="text-xs text-slate-500">{l.descripcion}</div>}</td>
                      <td className="px-3 py-1.5">{l.tercero}{l.tercero_documento && <div className="text-xs text-slate-500">{l.tercero_documento}</div>}</td>
                      <td className="px-3 py-1.5 text-right">{l.debito ? fmtCOP(l.debito) : ""}</td>
                      <td className="px-3 py-1.5 text-right">{l.credito ? fmtCOP(l.credito) : ""}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-50 font-semibold">
                  <tr><td className="px-3 py-2 text-right" colSpan={2}>Sumas iguales</td>
                    <td className="px-3 py-2 text-right">{fmtCOP(detalle.total_debito)}</td><td className="px-3 py-2 text-right">{fmtCOP(detalle.total_credito)}</td></tr>
                </tfoot>
              </table>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-700 mb-1">Traza de auditoría</h4>
              {auditoria.length === 0 ? <p className="text-xs text-slate-400">Sin eventos registrados</p> : (
                <ul className="text-xs text-slate-600 space-y-1">
                  {auditoria.map((a) => (
                    <li key={a.id} className="flex justify-between border-b border-slate-100 pb-1">
                      <span><span className="capitalize">{a.accion}</span> · {a.usuario_nombre || "—"}</span>
                      <span className="text-slate-400">{new Date(a.fecha_hora).toLocaleString("es-CO")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
