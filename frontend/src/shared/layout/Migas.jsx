import { Link, useLocation } from "react-router-dom";
import { moduloDeRuta, opcionDeRuta } from "../../core/menu.js";

/** Ruta de migas "Módulo › Opción" con regreso a la subpantalla del módulo. */
export default function Migas() {
  const { pathname } = useLocation();
  const modulo = moduloDeRuta(pathname);
  const opcion = opcionDeRuta(pathname);
  // Reportes maneja su propia ruta de migas por categoría.
  if (!modulo || !opcion || modulo.slug === "reportes") return null;
  return (
    <p className="text-sm text-geifem-blue mb-3">
      <Link to={`/${modulo.slug}`} className="hover:underline">‹ {modulo.titulo}</Link>
      <span className="text-slate-400"> › {opcion.titulo}</span>
    </p>
  );
}
