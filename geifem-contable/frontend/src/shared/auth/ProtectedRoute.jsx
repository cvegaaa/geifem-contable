import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export default function ProtectedRoute({ children, modulo, accion = "leer" }) {
  const { usuario, cargando, puede } = useAuth();
  const location = useLocation();

  if (cargando) {
    return <div className="p-8 text-slate-500">Cargando…</div>;
  }
  if (!usuario) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (modulo && !puede(modulo, accion)) {
    return (
      <div className="p-8 text-red-600">
        No tienes permiso para acceder a este módulo ({modulo}:{accion}).
      </div>
    );
  }
  return children;
}
