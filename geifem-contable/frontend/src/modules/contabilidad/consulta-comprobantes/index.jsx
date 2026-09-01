import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [tipo, setTipo] = useState("");
  const [rows, setRows] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [error, setError] = useState(null);

  const [detalle, setDetalle] = useState(null);
  const [auditoria, setAuditoria] = useState([]);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);

  const cargar = async () => {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (rango.desde) params.set("desde", rango.desde);
      if (rango.hasta) params.set("hasta", rango.hasta);
      if (tipo) params.set("tipo", tipo);
      const { data } = await api.get(`/api/contabilidad/comprobantes?${params}`);
      setRows(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
    api
      .get("/api/configuracion/plan-cuentas")
      .then((r) => setCuentas(r.data))
      .catch(() => {});
    // eslint-disable-next-line
  }, []);

  const nombreCuenta = (id) => {
    const c = cuentas.find((x) => x.id === id);
    return c ? `${c.codigo} — ${c.nombre}` : id;
  };

  const abrirDetalle = async (row) => {
    setCargandoDetalle(true);
    setDetalle(row);
    setAuditoria([]);
    try {
      const [det, aud] = await Promise.all([
        api.get(`/api/contabilidad/comprobantes/${row.id}`),
        api.get(`/api/contabilidad/auditoria?comprobante_id=${row.id}`),
      ]);
      setDetalle(det.data);
      setAuditoria(aud.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargandoDetalle(false);
    }
  };

  const sumas = detalle?.lineas
    ? detalle.lineas.reduce(
        (acc, l) => ({ debito: acc.debito + Number(l.debito || 0), credito: acc.credito + Number(l.credito || 0) }),
        { debito: 0, credito: 0 },
      )
    : { debito: 0, credito: 0 };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Consulta de comprobantes</h1>
      <div className="flex gap-3 mb-3 items-end flex-wrap">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Tipo</label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1 text-sm"
          >
            <option value="">Todos</option>
            <option value="ajuste">Ajuste</option>
            <option value="nota">Nota</option>
            <option value="apertura">Apertura</option>
            <option value="cierre">Cierre</option>
          </select>
        </div>
        <button onClick={cargar} className="px-3 py-1.5 bg-geifem-navy text-white text-sm rounded">
          Consultar
        </button>
      </div>
      {error && <div className="text-red-600 mb-2 text-sm">{error}</div>}
      <Table
        columns={[
          { key: "consecutivo", label: "#" },
          { key: "tipo", label: "Tipo" },
          { key: "fecha", label: "Fecha" },
          { key: "estado", label: "Estado" },
          { key: "descripcion", label: "Descripción" },
          {
            key: "acciones",
            label: "",
            render: (r) => (
              <button onClick={() => abrirDetalle(r)} className="text-geifem-blue hover:underline text-xs">
                Ver detalle
              </button>
            ),
          },
        ]}
        rows={rows}
      />

      <Modal
        open={!!detalle}
        onClose={() => setDetalle(null)}
        title={
          detalle
            ? `Comprobante #${detalle.consecutivo ?? ""} — ${detalle.tipo ?? ""}`
            : "Comprobante"
        }
        footer={
          <button onClick={() => setDetalle(null)} className="px-3 py-1.5 text-sm rounded border border-slate-300">
            Cerrar
          </button>
        }
      >
        {cargandoDetalle && <p className="text-sm text-slate-500">Cargando…</p>}
        {detalle && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-500">Fecha:</span> {detalle.fecha}</div>
              <div><span className="text-slate-500">Estado:</span> {detalle.estado}</div>
              <div className="col-span-2"><span className="text-slate-500">Descripción:</span> {detalle.descripcion || "—"}</div>
            </div>

            <div className="border border-slate-200 rounded overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="text-left px-3 py-2">Cuenta</th>
                    <th className="text-right px-3 py-2 w-28">Débito</th>
                    <th className="text-right px-3 py-2 w-28">Crédito</th>
                  </tr>
                </thead>
                <tbody>
                  {(detalle.lineas || []).map((l, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-1.5">
                        {nombreCuenta(l.cuenta_puc_id)}
                        {l.descripcion && <div className="text-xs text-slate-500">{l.descripcion}</div>}
                      </td>
                      <td className="px-3 py-1.5 text-right">{l.debito ? fmtCOP(l.debito) : ""}</td>
                      <td className="px-3 py-1.5 text-right">{l.credito ? fmtCOP(l.credito) : ""}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-50 font-semibold">
                  <tr>
                    <td className="px-3 py-2 text-right">Sumas iguales</td>
                    <td className="px-3 py-2 text-right">{fmtCOP(sumas.debito)}</td>
                    <td className="px-3 py-2 text-right">{fmtCOP(sumas.credito)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-slate-700 mb-1">Traza de auditoría</h4>
              {auditoria.length === 0 ? (
                <p className="text-xs text-slate-400">Sin eventos registrados</p>
              ) : (
                <ul className="text-xs text-slate-600 space-y-1">
                  {auditoria.map((a) => (
                    <li key={a.id} className="flex justify-between border-b border-slate-100 pb-1">
                      <span>{a.accion}</span>
                      <span className="text-slate-400">{a.fecha_hora}</span>
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
