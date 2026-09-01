import { createContext, useContext, useEffect, useState } from "react";
import api from "./api.js";
import { useAuth } from "../shared/auth/AuthContext.jsx";

const EmpresaContext = createContext(null);

export function EmpresaProvider({ children }) {
  const { usuario } = useAuth();
  const [empresas, setEmpresas] = useState([]);
  const [empresaId, setEmpresaId] = useState(
    () => localStorage.getItem("geifem_empresa_id") || null
  );

  useEffect(() => {
    if (!usuario) {
      setEmpresas([]);
      return;
    }
    api
      .get("/api/configuracion/datos-empresa")
      .then((r) => setEmpresas(r.data))
      .catch(() => setEmpresas([]));
  }, [usuario]);

  const cambiarEmpresa = (id) => {
    setEmpresaId(id);
    if (id) localStorage.setItem("geifem_empresa_id", id);
    else localStorage.removeItem("geifem_empresa_id");
  };

  return (
    <EmpresaContext.Provider value={{ empresas, empresaId, cambiarEmpresa }}>
      {children}
    </EmpresaContext.Provider>
  );
}

export function useEmpresa() {
  const ctx = useContext(EmpresaContext);
  if (!ctx) throw new Error("useEmpresa fuera de EmpresaProvider");
  return ctx;
}
