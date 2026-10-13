import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Avisos, SelectorCuenta, mensajeError } from "../../../shared/documentos/index.jsx";

/**
 * Qué cuenta del PUC usa cada asiento automático. Los productos, cajas y
 * bancos pueden tener cuentas propias; si no, se usan estas.
 */
export default function Page() {
  const { puede } = useAuth();
  const [filas, setFilas] = useState([]);
  const [plan, setPlan] = useState([]);
  const [valores, setValores] = useState({});
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = async () => {
    try {
      const [pr, pc] = await Promise.all([
        api.get("/api/configuracion/parametros-contables"),
        api.get("/api/configuracion/plan-cuentas"),
      ]);
      setFilas(pr.data);
      setValores(Object.fromEntries(pr.data.map((p) => [p.clave, p.codigo])));
      setPlan(pc.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const grupos = useMemo(() => {
    const out = {};
    for (const f of filas) (out[f.grupo] ||= []).push(f);
    return out;
  }, [filas]);

  const editable = puede("configuracion", "editar");

  const guardar = async () => {
    setError(null);
    setMensaje(null);
    setGuardando(true);
    try {
      await api.put("/api/configuracion/parametros-contables", { cuentas: valores });
      setMensaje("Parámetros guardados. Se aplican a los documentos que registres o edites desde ahora.");
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  };

  const restaurar = () => setValores(Object.fromEntries(filas.map((p) => [p.clave, p.por_defecto])));

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Parámetros contables</h1>
      <p className="text-sm text-slate-500 mb-4">
        Define qué cuenta usa cada asiento automático. Un producto, una caja o un banco con cuenta propia
        tiene prioridad sobre estos valores. Si necesitas una subcuenta (p. ej. 130505), créala primero en
        Plan de cuentas.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      {Object.entries(grupos).map(([grupo, items]) => (
        <section key={grupo} className="bg-white border border-slate-200 rounded-lg mb-4">
          <h2 className="px-4 py-2 border-b border-slate-200 font-semibold text-geifem-navy">{grupo}</h2>
          <div className="divide-y divide-slate-100">
            {items.map((p) => (
              <div key={p.clave} className="grid grid-cols-1 md:grid-cols-2 gap-2 items-center px-4 py-2">
                <div>
                  <div className="text-sm text-slate-700">{p.descripcion}</div>
                  {valores[p.clave] !== p.por_defecto && (
                    <div className="text-[11px] text-amber-700">Por defecto: {p.por_defecto}</div>
                  )}
                </div>
                <SelectorCuenta
                  cuentas={plan}
                  porCodigo
                  disabled={!editable}
                  value={valores[p.clave]}
                  onChange={(v) => setValores((prev) => ({ ...prev, [p.clave]: v }))}
                />
              </div>
            ))}
          </div>
        </section>
      ))}

      {editable && filas.length > 0 && (
        <div className="flex gap-2">
          <button onClick={guardar} disabled={guardando} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white disabled:opacity-50">
            {guardando ? "Guardando…" : "Guardar parámetros"}
          </button>
          <button onClick={restaurar} className="text-sm px-3 py-2 rounded-sm border border-slate-300">
            Restaurar valores por defecto
          </button>
        </div>
      )}
    </div>
  );
}
