import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import FormField, { Input } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, fmtCOP, mensajeError } from "../../../shared/documentos/index.jsx";

const GENERALES = [
  ["smmlv", "Salario mínimo mensual (SMMLV)"], ["aux_transporte", "Auxilio de transporte"], ["uvt", "Valor de la UVT"],
  ["horas_mes", "Horas del mes (divisor de la hora ordinaria)"], ["tope_aux_smmlv", "Tope del auxilio (en SMMLV)"],
  ["ibc_max_smmlv", "Tope del IBC (en SMMLV)"], ["tope_exoneracion_smmlv", "Tope de exoneración art. 114-1 (en SMMLV)"],
];
const PORCENTAJES = [
  ["salud_empleado", "Salud, empleado (%)"], ["pension_empleado", "Pensión, empleado (%)"],
  ["salud_empleador", "Salud, empleador (%)"], ["pension_empleador", "Pensión, empleador (%)"],
  ["caja", "Caja de compensación (%)"], ["sena", "SENA (%)"], ["icbf", "ICBF (%)"],
  ["cesantias", "Provisión de cesantías (%)"], ["intereses_cesantias", "Intereses sobre cesantías (% anual)"],
  ["prima", "Provisión de prima (%)"], ["vacaciones", "Provisión de vacaciones (%)"], ["incapacidad_porcentaje", "Incapacidad general (%)"],
];
const RECARGOS = {
  hora_extra_diurna: "Hora extra diurna", hora_extra_nocturna: "Hora extra nocturna", recargo_nocturno: "Recargo nocturno",
  recargo_dominical_festivo: "Recargo dominical o festivo", hora_extra_diurna_dominical: "Hora extra diurna dominical/festiva",
  hora_extra_nocturna_dominical: "Hora extra nocturna dominical/festiva", recargo_nocturno_dominical: "Recargo nocturno dominical/festivo",
};

export default function Page() {
  const { puede } = useAuth();
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/nomina/parametros", { params: { anio } });
      setP(data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [anio]);

  const num = (k) => (e) => setP({ ...p, [k]: Number(e.target.value) });
  const guardar = async () => {
    setError(null); setMensaje(null);
    try {
      const { data } = await api.put("/api/nomina/parametros", { valores: p }, { params: { anio } });
      setP(data);
      setMensaje(`Parámetros de ${anio} guardados y marcados como verificados. Aplican a las liquidaciones que crees o recalcules.`);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const editable = puede("nomina", "editar");
  if (!p) return <div className="text-slate-500">Cargando…</div>;

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Parámetros de nómina</h1>
      <p className="text-sm text-slate-500 mb-3">Cambian cada año o por norma. Cada liquidación usa los del año del periodo.</p>
      {!p.verificado && (
        <p className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
          Valores sugeridos, sin verificar. Confírmalos con el decreto de salario mínimo y auxilio, la resolución de la UVT, las leyes 2101 (jornada) y 2466
          (recargo dominical) y tu contador; luego guarda para marcarlos como verificados.
        </p>
      )}
      <Avisos error={error} mensaje={mensaje} />
      <div className="mb-4 w-32"><FormField label="Año"><Input type="number" value={anio} onChange={(e) => setAnio(Number(e.target.value))} /></FormField></div>

      <section className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h2 className="font-semibold text-geifem-navy mb-2">Generales</h2>
        <div className="grid sm:grid-cols-2 gap-x-4">
          {GENERALES.map(([k, n]) => (
            <FormField key={k} label={n}><Input type="number" step="any" disabled={!editable} value={p[k]} onChange={num(k)} /></FormField>
          ))}
        </div>
        <p className="text-xs text-slate-500">Tope del auxilio: {fmtCOP(p.tope_aux_smmlv * p.smmlv)} · Exoneración hasta {fmtCOP(p.tope_exoneracion_smmlv * p.smmlv)} de salario mensual.</p>
      </section>

      <section className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h2 className="font-semibold text-geifem-navy mb-2">Aportes y provisiones</h2>
        <div className="grid sm:grid-cols-3 gap-x-4">
          {PORCENTAJES.map(([k, n]) => (
            <FormField key={k} label={n}><Input type="number" step="any" disabled={!editable} value={p[k]} onChange={num(k)} /></FormField>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" disabled={!editable} checked={p.exonerado_114_1} onChange={(e) => setP({ ...p, exonerado_114_1: e.target.checked })} />
          Exonerado de salud del empleador, SENA e ICBF (art. 114-1 ET) para salarios menores al tope
        </label>
        <h3 className="text-sm font-semibold mt-4 mb-1">ARL por nivel de riesgo (%)</h3>
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(p.arl).map(([k, v]) => (
            <FormField key={k} label={`Riesgo ${k}`}><Input type="number" step="any" disabled={!editable} value={v} onChange={(e) => setP({ ...p, arl: { ...p.arl, [k]: Number(e.target.value) } })} /></FormField>
          ))}
        </div>
      </section>

      <section className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h2 className="font-semibold text-geifem-navy mb-1">Horas extra y recargos</h2>
        <p className="text-xs text-slate-500 mb-2">Factor que se paga sobre el valor de la hora ordinaria (1,25 = 125%). Los recargos solos (nocturno, dominical) se suman al sueldo mensual.</p>
        <div className="grid sm:grid-cols-2 gap-x-4">
          {Object.entries(RECARGOS).map(([k, n]) => (
            <FormField key={k} label={n}><Input type="number" step="any" disabled={!editable} value={p.recargos[k]} onChange={(e) => setP({ ...p, recargos: { ...p.recargos, [k]: Number(e.target.value) } })} /></FormField>
          ))}
        </div>
      </section>

      <section className="bg-white border border-slate-200 rounded-lg p-4 mb-4 text-xs text-slate-600">
        <h2 className="font-semibold text-geifem-navy text-sm mb-1">Tablas fijas (solo lectura)</h2>
        <p>Retención en la fuente laboral (art. 383 ET, en UVT): {p.tabla_retefuente.map((t) => `${t[0]}–${t[1] ?? "∞"}: ${t[2]}%`).join(" · ")}</p>
        <p>Fondo de solidaridad pensional (en SMMLV): {p.fsp.map((t) => `${t[0]}–${t[1] ?? "∞"}: ${t[2]}%`).join(" · ")}</p>
      </section>

      {editable && <button onClick={guardar} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm">Guardar y marcar como verificados</button>}
    </div>
  );
}
