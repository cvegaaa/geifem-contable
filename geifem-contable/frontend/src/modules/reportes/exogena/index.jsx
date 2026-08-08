import { Link } from "react-router-dom";
import { buscarCategoria } from "../_catalogo.js";

export default function Page() {
  const cat = buscarCategoria("exogena");
  const reportes = cat?.reportes || [];

  return (
    <div>
      <p className="text-sm text-geifem-blue mb-1">
        <Link to="/reportes">Reportes</Link> › Información exógena
      </p>
      <h1 className="text-2xl font-bold text-geifem-navy">Información exógena</h1>
      <p className="text-slate-500 mb-6">
        Genera los formatos de información exógena con los datos registrados en tu contabilidad.
        Cada formato agrupa la información por tercero identificado con tipo y número de documento.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {reportes.map((r) => (
          <Link
            key={r.slug}
            to={`/reportes/exogena/${r.slug}`}
            className="block bg-white border border-slate-200 rounded-lg p-4 hover:border-geifem-blue transition"
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="w-7 h-7 rounded bg-geifem-gold/20 text-geifem-gold-dark text-xs grid place-items-center font-bold">
                ▣
              </span>
              {r.exporta && (
                <span className="text-[11px] border border-slate-300 rounded px-1.5 py-0.5 text-slate-600">
                  {r.exporta}
                </span>
              )}
              {r.estado !== "activo" && (
                <span className="text-[11px] border border-slate-300 rounded px-1.5 py-0.5 text-slate-500">
                  Fase 3
                </span>
              )}
            </div>
            <h3 className="font-semibold text-geifem-navy">{r.titulo}</h3>
            <p className="text-sm text-slate-500 mt-1">{r.descripcion}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
