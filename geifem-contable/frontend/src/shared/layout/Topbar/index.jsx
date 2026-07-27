import { useAuth } from "../../auth/AuthContext.jsx";
import { useEmpresa } from "../../../core/EmpresaContext.jsx";

export default function Topbar() {
  const { usuario, logout } = useAuth();
  const { empresas, empresaId, cambiarEmpresa } = useEmpresa();

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <label className="text-xs text-slate-500 uppercase">Empresa:</label>
        <select
          value={empresaId || ""}
          onChange={(e) => cambiarEmpresa(e.target.value || null)}
          className="border border-slate-300 rounded px-2 py-1 text-sm"
        >
          <option value="">— sin selección —</option>
          {empresas.map((e) => (
            <option key={e.id} value={e.id}>
              {e.razon_social} ({e.nit})
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-sm text-right">
          <div className="font-medium text-slate-800">{usuario?.nombre}</div>
          <div className="text-xs text-slate-500 uppercase">{usuario?.rol}</div>
        </div>
        <button
          onClick={logout}
          className="text-sm bg-slate-100 hover:bg-slate-200 rounded px-3 py-1"
        >
          Salir
        </button>
      </div>
    </header>
  );
}
