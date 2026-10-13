import { NavLink } from "react-router-dom";
import MODULOS from "../../../core/menu.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import Logo from "../Logo/index.jsx";
import Icono from "../Icono/index.jsx";

// Solo módulos: sus opciones se abren en la subpantalla de cada módulo.
export default function Sidebar({ abierto = false, onCerrar = () => {} }) {
  const { puede } = useAuth();
  const visibles = MODULOS.filter((m) => puede(m.permiso, "leer"));

  const clase = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm ${
      isActive ? "bg-geifem-gold text-geifem-navy font-semibold" : "text-slate-200 hover:bg-white/10"
    }`;

  return (
    <>
    {abierto && <div className="fixed inset-0 bg-black/40 z-30 md:hidden no-imprimir" onClick={onCerrar} />}
    <aside
      className={`w-56 shrink-0 bg-geifem-navy text-white overflow-y-auto no-imprimir
        fixed inset-y-0 left-0 z-40 transition-transform md:static md:translate-x-0 ${abierto ? "translate-x-0" : "-translate-x-full"}`}
    >
      <div className="p-4 border-b border-white/10">
        <Logo variant="full" theme="light" size={40} />
      </div>
      <nav className="p-2 space-y-1">
        <NavLink to="/" end className={clase}>
          <Icono nombre="inicio" /> Inicio
        </NavLink>
        {visibles.map((m) => (
          <NavLink key={m.slug} to={`/${m.slug}`} className={clase}>
            <Icono nombre={m.icono} /> {m.titulo}
          </NavLink>
        ))}
      </nav>
    </aside>
    </>
  );
}
