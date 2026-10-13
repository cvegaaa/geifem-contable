import { Link } from "react-router-dom";
import MODULOS from "../../core/menu.js";
import Icono from "./Icono/index.jsx";

/** Subpantalla de un módulo: sus opciones como tarjetas. */
export default function ModuloHub({ slug }) {
  const modulo = MODULOS.find((m) => m.slug === slug);
  if (!modulo) return null;
  return (
    <div>
      <div className="flex items-center gap-3 mb-1 text-geifem-navy">
        <Icono nombre={modulo.icono} className="w-7 h-7" />
        <h1 className="text-2xl font-bold">{modulo.titulo}</h1>
      </div>
      <p className="text-slate-500 mb-6">{modulo.descripcion}</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {modulo.items.map((it) => (
          <Link
            key={it.to}
            to={it.to}
            className="block bg-white border border-slate-200 rounded-lg p-4 hover:border-geifem-blue hover:shadow-xs transition"
          >
            <h2 className="font-semibold text-geifem-navy">{it.titulo}</h2>
            <p className="text-sm text-slate-500 mt-1">{it.descripcion}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Tarjetas de todos los módulos visibles (pantalla de inicio). */
export function TarjetasModulos({ puede }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {MODULOS.filter((m) => puede(m.permiso, "leer")).map((m) => (
        <Link
          key={m.slug}
          to={`/${m.slug}`}
          className="flex gap-3 bg-white border border-slate-200 rounded-lg p-4 hover:border-geifem-blue transition"
        >
          <span className="text-geifem-blue"><Icono nombre={m.icono} className="w-6 h-6" /></span>
          <span>
            <span className="block font-semibold text-geifem-navy">{m.titulo}</span>
            <span className="block text-sm text-slate-500">{m.descripcion}</span>
          </span>
        </Link>
      ))}
    </div>
  );
}
