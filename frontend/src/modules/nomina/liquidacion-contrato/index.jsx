import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { AccionesDocumento, Avisos, EstadoBadge, fmtCOP, hoy, mensajeError, numeroDoc, useAnulacion } from "../../../shared/documentos/index.jsx";

const CAUSAS = [
  { valor: "renuncia", etiqueta: "Renuncia" },
  { valor: "mutuo_acuerdo", etiqueta: "Mutuo acuerdo" },
  { valor: "despido_sin_justa_causa", etiqueta: "Despido sin justa causa (con indemnización)" },
  { valor: "despido_con_justa_causa", etiqueta: "Despido con justa causa" },
  { valor: "terminacion_contrato_fijo", etiqueta: "Terminación de contrato a término fijo" },
];
const CONCEPTOS = [
  ["salario_pendiente", "Salario pendiente"], ["cesantias", "Cesantías"], ["intereses", "Intereses sobre cesantías"],
  ["prima", "Prima de servicios"], ["vacaciones", "Vacaciones"], ["indemnizacion", "Indemnización"],
];

export default function Page() {
  const { puede } = useAuth();
  const [empleados, setEmpleados] = useState([]);
  const [lista, setLista] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [form, setForm] = useState({ empleado_id: "", fecha_retiro: hoy(), causa: "renuncia", dias_salario_pendiente: 0, dias_vacaciones_disfrutados: "", promedio_variable: 0, fecha_fin_contrato: "" });
  const [vista, setVista] = useState(null);
  const [valores, setValores] = useState({});
  const [pagar, setPagar] = useState(null);
  const [pago, setPago] = useState({ cuenta: "", fecha: hoy() });
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const [e, l, c, b] = await Promise.all([
        api.get("/api/nomina/empleados"), api.get("/api/nomina/liquidaciones-finales"),
        api.get("/api/tesoreria/caja"), api.get("/api/tesoreria/bancos"),
      ]);
      setEmpleados(e.data.filter((x) => x.estado !== "retirado"));
      setLista(l.data);
      setCuentas([...c.data.map((x) => ({ ...x, tipo: "caja" })), ...b.data.map((x) => ({ ...x, tipo: "banco" }))]);
    } catch (err) {
      setError(mensajeError(err));
    }
  };
  useEffect(() => { cargar(); }, []);
  const anulacion = useAnulacion(() => { setMensaje("Liquidación anulada: el empleado vuelve a estar activo"); cargar(); });

  const cuerpo = (conValores = false) => ({
    empleado_id: form.empleado_id, fecha_retiro: form.fecha_retiro, causa: form.causa,
    dias_salario_pendiente: Number(form.dias_salario_pendiente || 0),
    dias_vacaciones_disfrutados: form.dias_vacaciones_disfrutados === "" ? null : Number(form.dias_vacaciones_disfrutados),
    promedio_variable: Number(form.promedio_variable || 0),
    fecha_fin_contrato: form.fecha_fin_contrato || null,
    valores: conValores ? Object.fromEntries(Object.entries(valores).map(([k, v]) => [k, Number(v || 0)])) : {},
  });

  const calcular = async () => {
    setError(null); setMensaje(null);
    if (!form.empleado_id) return setError("Selecciona el empleado");
    try {
      const { data } = await api.post("/api/nomina/liquidaciones-finales/calcular", cuerpo());
      setVista(data);
      setValores(Object.fromEntries(CONCEPTOS.map(([k]) => [k, data.calculo[k]])));
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const liquidar = async () => {
    if (!confirm("Se registrará el retiro del empleado y el asiento de la liquidación. ¿Continuar?")) return;
    try {
      const { data } = await api.post("/api/nomina/liquidaciones-finales", cuerpo(true));
      setMensaje(`${data.numero} registrada por ${fmtCOP(data.neto_pagar)}`);
      setVista(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const pagarLiquidacion = async () => {
    const c = cuentas.find((x) => x.id === pago.cuenta);
    if (!c) return setError("Selecciona la caja o el banco");
    try {
      const { data } = await api.post("/api/nomina/pagos", { documento_tipo: "liquidacion_final", documento_id: pagar.id, cuenta_tipo: c.tipo, cuenta_id: c.id, fecha: pago.fecha });
      setMensaje(`${data.numero} registrado`);
      setPagar(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const total = Object.values(valores).reduce((s, v) => s + Number(v || 0), 0);

  return (
    <div className="max-w-5xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Liquidación de contrato</h1>
      <p className="text-sm text-slate-500 mb-4">
        Calcula lo que se debe al empleado al retirarse (base 360 días), cancela sus provisiones y reconoce la diferencia en el gasto.
        Puedes ajustar cada valor antes de liquidar. No incluye aportes ni retención sobre el salario pendiente.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {puede("nomina", "crear") && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5">
          <div className="grid gap-x-3 sm:grid-cols-3">
            <FormField label="Empleado">
              <Select value={form.empleado_id} onChange={(e) => setForm({ ...form, empleado_id: e.target.value })}>
                <option value="">Seleccionar…</option>
                {empleados.map((e) => <option key={e.id} value={e.id}>{e.primer_nombre} {e.primer_apellido} ({e.numero_documento})</option>)}
              </Select>
            </FormField>
            <FormField label="Fecha de retiro"><Input type="date" value={form.fecha_retiro} onChange={(e) => setForm({ ...form, fecha_retiro: e.target.value })} /></FormField>
            <FormField label="Causa"><Select value={form.causa} onChange={(e) => setForm({ ...form, causa: e.target.value })}>{CAUSAS.map((c) => <option key={c.valor} value={c.valor}>{c.etiqueta}</option>)}</Select></FormField>
            <FormField label="Días de salario pendientes" hint="Días trabajados que no están en una liquidación de nómina."><Input type="number" min="0" value={form.dias_salario_pendiente} onChange={(e) => setForm({ ...form, dias_salario_pendiente: e.target.value })} /></FormField>
            <FormField label="Días de vacaciones ya disfrutados" hint="Vacío = se toman de las novedades registradas."><Input type="number" min="0" value={form.dias_vacaciones_disfrutados} onChange={(e) => setForm({ ...form, dias_vacaciones_disfrutados: e.target.value })} /></FormField>
            <FormField label="Promedio mensual de variables" hint="Horas extra, comisiones, etc. de los últimos 12 meses."><Input type="number" min="0" value={form.promedio_variable} onChange={(e) => setForm({ ...form, promedio_variable: e.target.value })} /></FormField>
            {form.causa === "despido_sin_justa_causa" && (
              <FormField label="Fin del contrato (solo término fijo)"><Input type="date" value={form.fecha_fin_contrato} onChange={(e) => setForm({ ...form, fecha_fin_contrato: e.target.value })} /></FormField>
            )}
          </div>
          <button onClick={calcular} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm">Calcular</button>
        </div>
      )}

      {vista && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6">
          <h2 className="font-semibold text-geifem-navy mb-2">{vista.empleado}</h2>
          <table className="w-full text-sm mb-3">
            <thead className="bg-slate-100"><tr><th className="text-left px-3 py-2">Concepto</th><th className="text-right px-3 py-2">Provisionado</th><th className="text-right px-3 py-2 w-48">Valor a pagar</th></tr></thead>
            <tbody>
              {CONCEPTOS.map(([k, n]) => (
                <tr key={k} className="border-t border-slate-100">
                  <td className="px-3 py-1.5">{n}</td>
                  <td className="px-3 py-1.5 text-right text-slate-500">{vista.provisionado[k] !== undefined ? fmtCOP(vista.provisionado[k]) : "—"}</td>
                  <td className="px-3 py-1"><Input type="number" min="0" className="text-right" value={valores[k] ?? ""} onChange={(e) => setValores({ ...valores, [k]: e.target.value })} /></td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50 font-semibold"><tr><td className="px-3 py-2" colSpan={2}>Total a pagar</td><td className="px-3 py-2 text-right text-geifem-navy">{fmtCOP(total)}</td></tr></tfoot>
          </table>
          <p className="text-xs text-slate-500 mb-3">
            Días: cesantías {vista.calculo.dias.cesantias}, prima {vista.calculo.dias.prima}, laborados {vista.calculo.dias.laborados}; vacaciones pendientes {vista.calculo.dias.vacaciones_pendientes}.
          </p>
          <div className="flex gap-2">
            <button onClick={liquidar} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm">Liquidar contrato</button>
            <button onClick={() => setVista(null)} className="border border-slate-300 text-sm px-3 py-2 rounded-sm">Cancelar</button>
          </div>
        </div>
      )}

      <Table
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
          { key: "empleado_nombre", label: "Empleado" }, { key: "fecha_retiro", label: "Retiro" },
          { key: "causa", label: "Causa", render: (r) => CAUSAS.find((c) => c.valor === r.causa)?.etiqueta },
          { key: "neto_pagar", label: "Total", render: (r) => fmtCOP(r.neto_pagar) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado === "anulado" ? "anulado" : r.pagado ? "pagada" : "pendiente de pago"} /> },
          { key: "_a", label: "", render: (r) => r.estado === "anulado" ? null : (
            <div className="flex gap-3">
              {!r.pagado && puede("nomina", "crear") && <button onClick={() => { setPagar(r); setPago({ cuenta: cuentas[0]?.id || "", fecha: hoy() }); }} className="text-xs text-emerald-700 hover:underline">Pagar</button>}
              {!r.pagado && <AccionesDocumento doc={r} modulo="nomina" onAnular={(d) => anulacion.pedir(d, `/api/nomina/liquidaciones-finales/${d.id}/anular`)} />}
            </div>
          ) },
        ]}
        rows={lista} empty="Aún no hay liquidaciones de contrato"
      />

      <Modal open={Boolean(pagar)} onClose={() => setPagar(null)} title={`Pagar ${pagar ? numeroDoc(pagar) : ""}`}
        footer={<><button onClick={() => setPagar(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button><button onClick={pagarLiquidacion} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Registrar pago</button></>}>
        <FormField label="Pagar desde"><Select value={pago.cuenta} onChange={(e) => setPago({ ...pago, cuenta: e.target.value })}><option value="">Seleccionar…</option>{cuentas.map((c) => <option key={c.id} value={c.id}>{c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre}</option>)}</Select></FormField>
        <FormField label="Fecha"><Input type="date" value={pago.fecha} onChange={(e) => setPago({ ...pago, fecha: e.target.value })} /></FormField>
      </Modal>
      {anulacion.modal}
    </div>
  );
}
