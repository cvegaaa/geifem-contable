import { useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import { useEmpresa } from "../../../core/EmpresaContext.jsx";
import { mensajeError } from "../../documentos/index.jsx";
import Modal from "../Modal/index.jsx";
import FormField, { Input } from "../FormField/index.jsx";
import Logo from "../Logo/index.jsx";

export default function Topbar({ onMenu }) {
  const { usuario, logout } = useAuth();
  const { empresas, empresaId, cambiarEmpresa } = useEmpresa();
  const [cuenta, setCuenta] = useState(false);
  const [claves, setClaves] = useState({ actual: "", nueva: "", repetir: "" });
  const [error, setError] = useState(null);
  const [listo, setListo] = useState(false);

  const cambiar = async () => {
    setError(null);
    if (claves.nueva.length < 8) return setError("La contraseña nueva debe tener al menos 8 caracteres");
    if (claves.nueva !== claves.repetir) return setError("Las contraseñas nuevas no coinciden");
    try {
      await api.post("/api/auth/cambiar-password", { actual: claves.actual, nueva: claves.nueva });
      setListo(true);
      setClaves({ actual: "", nueva: "", repetir: "" });
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const cerrar = () => {
    setCuenta(false);
    setListo(false);
    setError(null);
  };

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between gap-2 px-3 md:px-6 no-imprimir">
      <div className="flex items-center gap-3 md:gap-6 min-w-0">
        <button onClick={onMenu} className="md:hidden p-2 -ml-1 text-slate-600" aria-label="Abrir menú">
          <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <div className="hidden md:block"><Logo variant="mark" theme="dark" size={32} /></div>
        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <label className="hidden md:block text-xs text-slate-500 uppercase">Empresa:</label>
          <select
            value={empresaId || ""}
            onChange={(e) => cambiarEmpresa(e.target.value || null)}
            className="border border-slate-300 rounded-sm px-2 py-1 text-sm max-w-44 sm:max-w-xs truncate"
          >
            {empresas.map((e) => (
              <option key={e.id} value={e.id}>
                {e.razon_social} ({e.nit})
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex items-center gap-2 md:gap-4">
        <button onClick={() => setCuenta(true)} className="text-sm text-right hover:opacity-80" title="Mi cuenta">
          <div className="font-medium text-slate-800 max-w-28 sm:max-w-none truncate">{usuario?.nombre}</div>
          <div className="text-xs text-geifem-blue uppercase">{usuario?.rol}</div>
        </button>
        <button onClick={logout} className="text-sm bg-slate-100 hover:bg-slate-200 rounded-sm px-3 py-1">
          Salir
        </button>
      </div>

      <Modal
        open={cuenta} onClose={cerrar} title="Mi cuenta"
        footer={<>
          <button onClick={cerrar} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">{listo ? "Cerrar" : "Cancelar"}</button>
          {!listo && <button onClick={cambiar} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Cambiar contraseña</button>}
        </>}
      >
        <p className="text-sm mb-3"><b>{usuario?.nombre}</b><br /><span className="text-slate-500">{usuario?.email}</span></p>
        {listo ? (
          <p className="text-sm text-emerald-700">Contraseña actualizada. Tus otras sesiones abiertas se cerraron.</p>
        ) : (
          <>
            <FormField label="Contraseña actual"><Input type="password" autoComplete="current-password" value={claves.actual} onChange={(e) => setClaves({ ...claves, actual: e.target.value })} /></FormField>
            <FormField label="Contraseña nueva" hint="Mínimo 8 caracteres"><Input type="password" autoComplete="new-password" value={claves.nueva} onChange={(e) => setClaves({ ...claves, nueva: e.target.value })} /></FormField>
            <FormField label="Repite la contraseña nueva"><Input type="password" autoComplete="new-password" value={claves.repetir} onChange={(e) => setClaves({ ...claves, repetir: e.target.value })} /></FormField>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </>
        )}
      </Modal>
    </header>
  );
}
