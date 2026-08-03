import { Link, useParams } from "react-router-dom";
import CATALOGO, { buscarCategoria } from "./_catalogo.js";

function Tarjeta({ categoriaSlug, r }) {
  return (
    <Link
      to={`/reportes/${categoriaSlug}/${r.slug}`}
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
            {r.estado === "fase2" ? "Fase 2" : "Fase 3"}
          </span>
        )}
      </div>
      <h3 className="font-semibold text-geifem-navy">{r.titulo}</h3>
      <p className="text-sm text-slate-500 mt-1">{r.descripcion}</p>
    </Link>
  );
}

export function CategoriaReportes() {
  const { categoria } = useParams();
  const cat = buscarCategoria(categoria);
  if (!cat) return <p className="text-slate-500">Categoría no encontrada.</p>;
  return (
    <div>
      <p className="text-sm text-geifem-blue mb-1">
        <Link to="/reportes">Reportes</Link> › {cat.titulo}
      </p>
      <h1 className="text-2xl font-bold text-geifem-navy">{cat.titulo}</h1>
      <p className="text-slate-500 mb-6">{cat.descripcion}</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cat.reportes.map((r) => (
          <Tarjeta key={r.slug} categoriaSlug={cat.slug} r={r} />
        ))}
      </div>
    </div>
  );
}

export default function IndiceReportes() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-geifem-navy mb-1">Reportes</h1>
      <p className="text-slate-500 mb-6">
        Selecciona una categoría para consultar y exportar la información de tu empresa.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {CATALOGO.map((c) => (
          <Link
            key={c.slug}
            to={`/reportes/${c.slug}`}
            className="block bg-white border border-slate-200 rounded-lg p-4 hover:border-geifem-blue transition"
          >
            <h2 className="font-semibold text-geifem-navy">{c.titulo}</h2>
            <p className="text-sm text-slate-500 mt-1">{c.descripcion}</p>
            <p className="text-xs text-slate-400 mt-2">{c.reportes.length} reportes</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
