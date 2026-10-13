import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { useEmpresa } from "../../../core/EmpresaContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { AccionesDocumento, Avisos, EstadoBadge, fmtCOP, hoy, mensajeError, numeroDoc, useAnulacion } from "../../../shared/documentos/index.jsx";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const TIPOS = { mensual: "Mensual", quincena1: "Primera quincena", quincena2: "Segunda quincena" };

const nombreHora = {
  hora_extra_diurna: "Hora extra diurna", hora_extra_nocturna: "Hora extra nocturna", recargo_nocturno: "Recargo nocturno",
  recargo_dominical_festivo: "Recargo dominical/festivo", hora_extra_diurna_dominical: "H. extra diurna dominical",
  hora_extra_nocturna_dominical: "H. extra nocturna dominical", recargo_nocturno_dominical: "Recargo nocturno dominical",
};

function Desprendible({ periodo, linea, empresa }) {
  const d = linea.devengos;
  const filas = [
    ["Sueldo", d.sueldo, linea.dias_trabajados ? `${linea.dias_trabajados} días` : ""],
    ["Auxilio de transporte", d.aux_transporte],
    ["Vacaciones", d.vacaciones], ["Licencia remunerada", d.licencia_remunerada],
    ["Incapacidad (empleador)", d.incapacidad_empleador], ["Incapacidad / licencia (EPS o ARL)", d.incapacidad_a_cargo_eps_arl],
    ...Object.entries(d.horas).map(([k, v]) => [nombreHora[k] || k, v]),
    ["Comisiones", d.comisiones], ["Bonificación salarial", d.bonificacion_salarial], ["Devengos no salariales", d.no_salariales],
  ].filter((f) => f[1]);
  const ded = [
    ["Salud (4%)", linea.deducciones.salud], ["Pensión (4%)", linea.deducciones.pension],
    ["Fondo de solidaridad pensional", linea.deducciones.fsp], ["Retención en la fuente", linea.deducciones.retefuente],
    ...linea.deducciones.otras.map((o) => [o.tipo, o.valor]),
  ].filter((f) => f[1]);
  return (
    <div className="imprimible bg-white p-6 text-sm">
      <div className="flex justify-between border-b border-slate-300 pb-2 mb-3">
        <div>
          <div className="text-lg font-bold">{empresa?.razon_social}</div>
          <div className="text-xs text-slate-500">NIT {empresa?.nit}</div>
        </div>
        <div className="text-right">
          <div className="font-semibold">Desprendible de pago</div>
          <div className="text-xs text-slate-500">{numeroDoc(periodo)} · {periodo.fecha_inicio} a {periodo.fecha_fin}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div><span className="text-slate-500">Empleado:</span> <b>{linea.nombre}</b></div>
        <div><span className="text-slate-500">Documento:</span> {linea.documento}</div>
        <div><span className="text-slate-500">Salario básico:</span> {fmtCOP(linea.salario_basico)}</div>
        <div><span className="text-slate-500">IBC:</span> {fmtCOP(linea.ibc)}</div>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div>
          <div className="font-semibold border-b border-slate-300 mb-1">Devengado</div>
          {filas.map(([n, v, extra]) => (
            <div key={n} className="flex justify-between"><span>{n} {extra && <span className="text-xs text-slate-400">{extra}</span>}</span><span>{fmtCOP(v)}</span></div>
          ))}
          <div className="flex justify-between font-semibold border-t border-slate-300 mt-1 pt-1"><span>Total devengado</span><span>{fmtCOP(linea.total_devengado)}</span></div>
        </div>
        <div>
          <div className="font-semibold border-b border-slate-300 mb-1">Deducciones</div>
          {ded.length === 0 && <div className="text-slate-400">Sin deducciones</div>}
          {ded.map(([n, v]) => (
            <div key={n} className="flex justify-between"><span>{n}</span><span>{fmtCOP(v)}</span></div>
          ))}
          <div className="flex justify-between font-semibold border-t border-slate-300 mt-1 pt-1"><span>Total deducciones</span><span>{fmtCOP(linea.total_deducciones)}</span></div>
        </div>
      </div>
      <div className="flex justify-between text-base font-bold border-t-2 border-slate-400 mt-4 pt-2">
        <span>Neto a pagar</span><span>{fmtCOP(linea.neto_pagar)}</span>
      </div>
    </div>
  );
}

export default function Page() {
  const { puede } = useAuth();
  const { empresaActiva } = useEmpresa();
  const [periodos, setPeriodos] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [detalle, setDetalle] = useState(null);
  const [imprimir, setImprimir] = useState(null);
  const [pagar, setPagar] = useState(null);
  const [pago, setPago] = useState({ cuenta: "", fecha: hoy() });
  const [form, setForm] = useState({ anio: new Date().getFullYear(), mes: new Date().getMonth() + 1, tipo: "mensual" });
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [trabajando, setTrabajando] = useState(false);

  const cargar = async () => {
    try {
      const [p, caja, banco] = await Promise.all([
        api.get("/api/nomina/periodos"), api.get("/api/tesoreria/caja"), api.get("/api/tesoreria/bancos"),
      ]);
      setPeriodos(p.data);
      setCuentas([...caja.data.map((c) => ({ ...c, tipo: "caja" })), ...banco.data.map((c) => ({ ...c, tipo: "banco" }))]);
    } catch (err) {
      setError(mensajeError(err));
    }
  };
  useEffect(() => { cargar(); }, []);

  const anulacion = useAnulacion(() => { setMensaje("Liquidación anulada"); setDetalle(null); cargar(); });

  const liquidar = async () => {
    setError(null); setMensaje(null); setTrabajando(true);
    try {
      const { data } = await api.post("/api/nomina/periodos", { ...form, anio: Number(form.anio), mes: Number(form.mes) });
      setMensaje(`${data.numero} liquidada: ${data.totales.empleados} empleado(s), neto ${fmtCOP(data.totales.neto_pagar)}`);
      cargar();
      verDetalle(data.id);
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setTrabajando(false);
    }
  };

  const verDetalle = async (id) => {
    try {
      const { data } = await api.get(`/api/nomina/periodos/${id}`);
      setDetalle(data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const recalcular = async (p) => {
    setError(null); setMensaje(null);
    try {
      await api.put(`/api/nomina/periodos/${p.id}`, { anio: p.anio, mes: p.mes, tipo: p.tipo });
      setMensaje(`${p.numero} recalculada con los datos actuales`);
      cargar();
      if (detalle?.id === p.id) verDetalle(p.id);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const pagarNomina = async () => {
    const cuenta = cuentas.find((c) => c.id === pago.cuenta);
    if (!cuenta) return setError("Selecciona la caja o el banco desde el que pagas");
    try {
      const { data } = await api.post("/api/nomina/pagos", {
        documento_tipo: "periodo", documento_id: pagar.id, cuenta_tipo: cuenta.tipo, cuenta_id: cuenta.id, fecha: pago.fecha,
      });
      setMensaje(`${data.numero} registrado por ${fmtCOP(data.valor)}`);
      setPagar(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anularPago = async (p) => {
    if (!confirm(`¿Anular el pago de ${p.numero}? La liquidación quedará pendiente de pago.`)) return;
    try {
      await api.post(`/api/nomina/pagos/${p.pago_id}/anular`, {});
      setMensaje("Pago anulado");
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const columnas = [
    { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
    { key: "periodo", label: "Periodo", render: (r) => `${MESES[r.mes - 1]} ${r.anio} · ${TIPOS[r.tipo]}` },
    { key: "empleados", label: "Empleados", render: (r) => r.totales?.empleados },
    { key: "devengado", label: "Devengado", render: (r) => fmtCOP(r.totales?.total_devengado) },
    { key: "neto", label: "Neto a pagar", render: (r) => fmtCOP(r.totales?.neto_pagar) },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado === "anulado" ? "anulado" : r.pagado ? `pagada ${r.fecha_pago || ""}` : "pendiente de pago"} /> },
    {
      key: "_acciones", label: "",
      render: (r) => (
        <div className="flex gap-3 items-center whitespace-nowrap">
          <button onClick={() => verDetalle(r.id)} className="text-xs text-geifem-blue hover:underline">Ver</button>
          {r.estado !== "anulado" && !r.pagado && puede("nomina", "crear") && (
            <button onClick={() => { setPagar(r); setPago({ cuenta: cuentas[0]?.id || "", fecha: hoy() }); }} className="text-xs text-emerald-700 hover:underline">Pagar</button>
          )}
          {r.estado !== "anulado" && r.pagado && puede("nomina", "inactivar") && (
            <button onClick={() => anularPago(r)} className="text-xs text-amber-700 hover:underline">Anular pago</button>
          )}
          {r.estado !== "anulado" && !r.pagado && puede("nomina", "editar") && (
            <button onClick={() => recalcular(r)} className="text-xs text-geifem-blue hover:underline">Recalcular</button>
          )}
          {r.estado !== "anulado" && !r.pagado && (
            <AccionesDocumento doc={r} modulo="nomina" onAnular={(d) => anulacion.pedir(d, `/api/nomina/periodos/${d.id}/anular`)} />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Liquidación de nómina</h1>
      <p className="text-sm text-slate-500 mb-4">
        Liquida el mes (empleados con pago mensual) o cada quincena (empleados con pago quincenal). La retención en la fuente de los
        quincenales se practica en la segunda quincena sobre lo acumulado del mes. Cada liquidación genera su asiento y las provisiones.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {puede("nomina", "crear") && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5 flex flex-wrap gap-3 items-end">
          <FormField label="Año"><Input type="number" value={form.anio} onChange={(e) => setForm({ ...form, anio: e.target.value })} /></FormField>
          <FormField label="Mes">
            <Select value={form.mes} onChange={(e) => setForm({ ...form, mes: e.target.value })}>
              {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </Select>
          </FormField>
          <FormField label="Periodo">
            <Select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </FormField>
          <button onClick={liquidar} disabled={trabajando} className="mb-3 bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60">
            {trabajando ? "Liquidando…" : "Liquidar periodo"}
          </button>
        </div>
      )}

      <Table titulo="Liquidaciones de nómina" columns={columnas} rows={periodos} empty="Aún no hay liquidaciones" />

      {detalle && (
        <div className="mt-6 bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex justify-between items-start mb-2">
            <h2 className="font-semibold text-geifem-navy">{numeroDoc(detalle)} · {MESES[detalle.mes - 1]} {detalle.anio} · {TIPOS[detalle.tipo]}</h2>
            <button onClick={() => setDetalle(null)} className="text-slate-400 hover:text-slate-700">✕</button>
          </div>
          {!detalle.parametros_verificados && (
            <p className="mb-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
              Los parámetros de nómina de {detalle.anio} no han sido confirmados: revisa Parámetros de nómina (salario mínimo, auxilio, recargos, UVT)
              y guarda para marcarlos como verificados.
            </p>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm mb-3">
            <div>Devengado <b>{fmtCOP(detalle.totales.total_devengado)}</b></div>
            <div>Deducciones <b>{fmtCOP(detalle.totales.total_deducciones)}</b></div>
            <div>Neto <b>{fmtCOP(detalle.totales.neto_pagar)}</b></div>
            <div>Retención en la fuente <b>{fmtCOP(detalle.totales.retefuente)}</b></div>
            <div>Seguridad social empleador <b>{fmtCOP(detalle.totales.seguridad_social_empleador)}</b></div>
            <div>Parafiscales <b>{fmtCOP(detalle.totales.parafiscales)}</b></div>
            <div>Provisiones <b>{fmtCOP(detalle.totales.cesantias + detalle.totales.intereses + detalle.totales.prima + detalle.totales.vacaciones)}</b></div>
            <div>A cargo de EPS/ARL <b>{fmtCOP(detalle.totales.a_cargo_eps_arl)}</b></div>
          </div>
          <Table titulo="Detalle de la liquidación"
            columns={[
              { key: "nombre", label: "Empleado" },
              { key: "dias_trabajados", label: "Días" },
              { key: "devengado", label: "Devengado", render: (l) => fmtCOP(l.total_devengado) },
              { key: "deducciones", label: "Deducciones", render: (l) => fmtCOP(l.total_deducciones) },
              { key: "neto", label: "Neto", render: (l) => <b>{fmtCOP(l.neto_pagar)}</b> },
              { key: "_p", label: "", render: (l) => <button onClick={() => setImprimir(l)} className="text-xs text-geifem-blue hover:underline">Desprendible</button> },
            ]}
            rows={detalle.lineas.map((l) => ({ ...l, id: l.empleado_id }))}
          />
        </div>
      )}

      <Modal
        open={Boolean(pagar)} onClose={() => setPagar(null)} title={`Pagar ${pagar ? numeroDoc(pagar) : ""}`}
        footer={<>
          <button onClick={() => setPagar(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
          <button onClick={pagarNomina} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Registrar pago</button>
        </>}
      >
        {pagar && <p className="text-sm mb-3">Neto a pagar: <b>{fmtCOP(pagar.totales.neto_pagar)}</b>. Genera el egreso de caja o banco y cancela salarios por pagar.</p>}
        <FormField label="Pagar desde">
          <Select value={pago.cuenta} onChange={(e) => setPago({ ...pago, cuenta: e.target.value })}>
            <option value="">Seleccionar…</option>
            {cuentas.map((c) => <option key={c.id} value={c.id}>{c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre} ({fmtCOP(c.saldo)})</option>)}
          </Select>
        </FormField>
        <FormField label="Fecha de pago" hint="Es la fecha que se reporta a la DIAN en la nómina electrónica.">
          <Input type="date" value={pago.fecha} onChange={(e) => setPago({ ...pago, fecha: e.target.value })} />
        </FormField>
      </Modal>

      <Modal
        open={Boolean(imprimir)} onClose={() => setImprimir(null)} title="Desprendible de pago"
        footer={<>
          <button onClick={() => setImprimir(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm no-imprimir">Cerrar</button>
          <button onClick={() => window.print()} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm no-imprimir">Imprimir</button>
        </>}
      >
        {imprimir && detalle && <Desprendible periodo={detalle} linea={imprimir} empresa={empresaActiva} />}
      </Modal>
      {anulacion.modal}
    </div>
  );
}
