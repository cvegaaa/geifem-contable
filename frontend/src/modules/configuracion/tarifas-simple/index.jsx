import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Input } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

export default function Page() {
  const { puede } = useAuth();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const editable = puede("configuracion", "editar");

  useEffect(() => {
    api.get("/api/configuracion/tarifas-simple").then((r) => setDatos(r.data)).catch((e) => setError(mensajeError(e)));
  }, []);

  const cambiar = (g, i, campo, valor) =>
    setDatos((d) => ({
      ...d,
      grupos: { ...d.grupos, [g]: { ...d.grupos[g], tramos: d.grupos[g].tramos.map((t, k) => (k === i ? { ...t, [campo]: valor } : t)) } },
    }));

  const guardar = async () => {
    setError(null);
    setMensaje(null);
    try {
      const grupos = Object.fromEntries(Object.entries(datos.grupos).map(([g, v]) => [g, {
        ...v, tramos: v.tramos.map((t) => ({ hasta_uvt: Number(t.hasta_uvt), tarifa: Number(t.tarifa) })),
      }]));
      const { data } = await api.put("/api/configuracion/tarifas-simple", { verificado: datos.verificado, grupos });
      setDatos(data);
      setMensaje("Tarifas guardadas");
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  if (!datos) return <Avisos error={error} />;

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Tarifas del régimen SIMPLE</h1>
      <p className="text-sm text-slate-500 mb-4">
        Tarifa consolidada por grupo de actividad según los ingresos brutos acumulados del año (en UVT). Se usa en los formularios 2593 y 260.
        Los valores iniciales son de referencia (art. 908 ET): confírmalos con tu contador y márcalos como verificados.
      </p>
      <Avisos error={error} mensaje={mensaje} />
      {Object.entries(datos.grupos).map(([g, v]) => (
        <section key={g} className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
          <h2 className="font-semibold text-geifem-navy mb-2">Grupo {g} · {v.nombre}</h2>
          <table className="text-sm">
            <thead><tr><th className="text-left pr-6">Ingresos hasta (UVT)</th><th className="text-left">Tarifa %</th></tr></thead>
            <tbody>
              {v.tramos.map((t, i) => (
                <tr key={i}>
                  <td className="pr-6 py-1"><Input type="number" disabled={!editable} value={t.hasta_uvt} onChange={(e) => cambiar(g, i, "hasta_uvt", e.target.value)} /></td>
                  <td className="py-1"><Input type="number" step="any" disabled={!editable} value={t.tarifa} onChange={(e) => cambiar(g, i, "tarifa", e.target.value)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {editable && (
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={datos.verificado} onChange={(e) => setDatos({ ...datos, verificado: e.target.checked })} />
            Verificadas por el contador
          </label>
          <button onClick={guardar} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white">Guardar tarifas</button>
        </div>
      )}
    </div>
  );
}
