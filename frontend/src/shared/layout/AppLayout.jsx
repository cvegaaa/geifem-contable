import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useEmpresa } from "../../core/EmpresaContext.jsx";
import Sidebar from "./Sidebar/index.jsx";
import Topbar from "./Topbar/index.jsx";
import Migas from "./Migas.jsx";
import { VistaDocumentoProvider } from "../documentos/Imprimible.jsx";

export default function AppLayout() {
  const { empresaId } = useEmpresa();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { pathname } = useLocation();

  // En pantallas pequeñas el menú se cierra al navegar.
  useEffect(() => setMenuAbierto(false), [pathname]);

  return (
    <VistaDocumentoProvider>
      <div className="min-h-screen flex bg-slate-50">
        <Sidebar abierto={menuAbierto} onCerrar={() => setMenuAbierto(false)} />
        <div className="flex-1 flex flex-col min-w-0">
          <Topbar onMenu={() => setMenuAbierto(true)} />
          <main className="flex-1 p-3 sm:p-6 overflow-auto">
            <Migas />
            {/* Cambiar de empresa remonta la vista para recargar sus datos. */}
            <Outlet key={empresaId || "sin-empresa"} />
          </main>
        </div>
      </div>
    </VistaDocumentoProvider>
  );
}
