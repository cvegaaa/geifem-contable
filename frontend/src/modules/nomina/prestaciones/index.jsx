import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { AccionesDocumento, Avisos, EstadoBadge, fmtCOP, hoy, mensajeError, numeroDoc, useAnulacion } from "../../../shared/documentos/index.jsx";

const TABS = [
  { clave: "prima", titulo: "Prima de servicios", ayuda: "Se paga en junio y diciembre." },
  { clave: "cesantias", titulo: "Cesantías", ayuda: "Se consignan al fondo antes del 14 de febrero." },
  { clave: "intereses", titulo: "Intereses sobre cesantías", ayuda: "Se pagan al empleado en enero." },
  { clave: "vacaciones", titulo: "Vacaciones", ayuda: "Pago de vacaciones provisionadas (compensadas en dinero o liquidadas)." },
  { clave: "seguridad_social", titulo: "Seguridad social (PILA)", ayuda: "Aportes de salud, pensión, ARL, caja, SENA e ICBF del mes." },
];
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function descargarCsv(pila) {
  const cab = ["Documento", "Nombre", "Días", "IBC", "Salud empleado", "Pensión empleado", "Solidaridad", "Salud empleador", "Pensión empleador", "ARL", "Caja", "SENA", "ICBF"];
  const filas = pila.filas.map((f) => [f.documento, f.nombre, f.dias, f.ibc, f.salud_empleado, f.pension_empleado, f.fsp, f.salud_empleador, f.pension_empleador, f.arl, f.caja, f.sena, f.icbf]);
  const csv = [cab, ...filas].map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(";")).join("\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `pila-${pila.anio}-${String(pila.mes).padStart(2, "0")}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Page() {
  const { puede } = useAuth();
  const [tab, setTab] = useState("prima");
  const [filas, setFilas] = useState([]);
  const [valores, setValores] = useState({});
  const [pila, setPila] = useState(null);
  const [periodo, setPeriodo] = useState({ anio: new Date().getFullYear(), mes: new Date().getMonth() + 1 });
  const [cuentas, setCuentas] = useState([]);
  const [cuenta, setCuenta] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [historial, setHistorial] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargarHistorial = () => api.get("/api/nomina/pagos-obligaciones").then((r) => setHistorial(r.data)).catch(() => {});

  const cargar = async () => {
    setError(null);
    try {
      if (tab === "seguridad_social") {
        const { data } = await api.get("/api/nomina/pila", { params: periodo });
        setPila(data);
      } else {
        const { data } = await api.get("/api/nomina/obligaciones", { params: { tipo: tab } });
        setFilas(data.filas);
        setValores(Object.fromEntries(data.filas.map((f) => [f.empleado_id, f.saldo])));
      }
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [tab, periodo.anio, periodo.mes]);
  useEffect(() => {
    Promise.all([api.get("/api/tesoreria/caja"), api.get("/api/tesoreria/bancos")]).then(([c, b]) =>
      setCuentas([...c.data.map((x) => ({ ...x, tipo: "caja" })), ...b.data.map((x) => ({ ...x, tipo: "banco" }))])).catch(() => {});
    cargarHistorial();
  }, []);

  const anulacion = useAnulacion(() => { setMensaje("Pago anulado"); cargar(); cargarHistorial(); });

  const pagar = async () => {
    setError(null); setMensaje(null);
    const c = cuentas.find((x) => x.id === cuenta);
    if (!c) return setError("Selecciona la caja o el banco desde el que pagas");
    const cuerpo = { tipo: tab, fecha, cuenta_tipo: c.tipo, cuenta_id: c.id };
    if (tab === "seguridad_social") Object.assign(cuerpo, periodo);
    else {
      cuerpo.lineas = filas.map((f) => ({ empleado_id: f.empleado_id, valor: Number(valores[f.empleado_id] || 0) })).filter((l) => l.valor > 0);
      if (!cuerpo.lineas.length) return setError("Indica al menos un valor a pagar");
    }
    try {
      const { data } = await api.post("/api/nomina/pagos-obligaciones", cuerpo);
      setMensaje(`${data.numero} registrado por ${fmtCOP(data.valor)}`);
      cargar(); cargarHistorial();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const actual = TABS.find((t) => t.clave === tab);
  const totalPago = tab === "seguridad_social" ? pila?.pendiente : filas.reduce((s, f) => s + Number(valores[f.empleado_id] || 0), 0);

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Prestaciones y seguridad social</h1>
      <p className="text-sm text-slate-500 mb-4">Pagos que cancelan lo provisionado en cada liquidación: cada uno genera su egreso y su asiento.</p>
      <Avisos error={error} mensaje={mensaje} />

      <div className="flex flex-wrap gap-1 mb-4 border-b border-slate-200">
        {TABS.map((t) => (
          <button key={t.clave} onClick={() => setTab(t.clave)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === t.clave ? "border-geifem-navy text-geifem-navy font-semibold" : "border-transparent text-slate-500"}`}>
            {t.titulo}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500 mb-3">{actual.ayuda}</p>

      {tab === "seguridad_social" ? (
        <>
          <div className="flex gap-3 items-end mb-3">
            <FormField label="Año"><Input type="number" value={periodo.anio} onChange={(e) => setPeriodo({ ...periodo, anio: Number(e.target.value) })} /></FormField>
            <FormField label="Mes">
              <Select value={periodo.mes} onChange={(e) => setPeriodo({ ...periodo, mes: Number(e.target.value) })}>
                {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </Select>
            </FormField>
            {pila && pila.filas.length > 0 && (
              <button onClick={() => descargarCsv(pila)} className="mb-3 border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm">Descargar CSV de soporte</button>
            )}
          </div>
          {pila && (
            <>
              <Table titulo="Aportes PILA"
                columns={[
                  { key: "nombre", label: "Empleado" }, { key: "dias", label: "Días" },
                  { key: "ibc", label: "IBC", render: (f) => fmtCOP(f.ibc) },
                  { key: "emp", label: "Aportes empleado", render: (f) => fmtCOP(f.salud_empleado + f.pension_empleado + f.fsp) },
                  { key: "empl", label: "Aportes empleador", render: (f) => fmtCOP(f.salud_empleador + f.pension_empleador + f.arl + f.caja + f.sena + f.icbf) },
                ]}
                rows={pila.filas.map((f) => ({ ...f, id: f.empleado_id }))} empty="No hay nómina liquidada en ese mes"
              />
              <p className="text-sm mt-2">Total aportes <b>{fmtCOP(pila.total)}</b> · pagado <b>{fmtCOP(pila.pagado)}</b> · pendiente <b>{fmtCOP(pila.pendiente)}</b></p>
              <p className="text-xs text-slate-400">Este soporte no reemplaza el archivo plano del operador de información (PILA).</p>
            </>
          )}
        </>
      ) : (
        <Table titulo="Saldos de prestaciones"
          columns={[
            { key: "nombre", label: "Empleado" }, { key: "documento", label: "Documento" },
            { key: "saldo", label: "Provisionado", render: (f) => fmtCOP(f.saldo) },
            { key: "pagar", label: "Valor a pagar", render: (f) => (
              <Input type="number" min="0" className="text-right w-36" value={valores[f.empleado_id] ?? ""}
                onChange={(e) => setValores({ ...valores, [f.empleado_id]: e.target.value })} />
            ) },
          ]}
          rows={filas.map((f) => ({ ...f, id: f.empleado_id }))} empty="No hay saldos provisionados de esta prestación"
        />
      )}

      {puede("nomina", "crear") && totalPago > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 mt-4 flex flex-wrap gap-3 items-end">
          <FormField label="Pagar desde">
            <Select value={cuenta} onChange={(e) => setCuenta(e.target.value)}>
              <option value="">Seleccionar…</option>
              {cuentas.map((c) => <option key={c.id} value={c.id}>{c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre}</option>)}
            </Select>
          </FormField>
          <FormField label="Fecha"><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></FormField>
          <button onClick={pagar} className="mb-3 bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm">Pagar {fmtCOP(totalPago)}</button>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-700 mt-8 mb-2">Pagos registrados</h2>
      <Table titulo="Pagos de prestaciones y aportes"
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
          { key: "fecha", label: "Fecha" },
          { key: "tipo", label: "Concepto", render: (r) => TABS.find((t) => t.clave === r.tipo)?.titulo || r.tipo },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          { key: "_a", label: "", render: (r) => <AccionesDocumento doc={r} modulo="nomina" onAnular={(d) => anulacion.pedir(d, `/api/nomina/pagos-obligaciones/${d.id}/anular`)} /> },
        ]}
        rows={historial} empty="Aún no hay pagos"
      />
      {anulacion.modal}
    </div>
  );
}
