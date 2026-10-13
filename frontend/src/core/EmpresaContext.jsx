import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "./api.js";
import { useAuth } from "../shared/auth/AuthContext.jsx";

const EmpresaContext = createContext(null);

export function EmpresaProvider({ children }) {
  const { usuario } = useAuth();
  const [empresas, setEmpresas] = useState([]);
  // Qué impuestos y retenciones puede parametrizar la empresa activa (lo calcula el servidor).
  const [perfil, setPerfil] = useState(null);
  const [empresaId, setEmpresaId] = useState(
    () => localStorage.getItem("geifem_empresa_id") || null
  );

  const cambiarEmpresa = useCallback((id) => {
    setEmpresaId(id);
    if (id) localStorage.setItem("geifem_empresa_id", id);
    else localStorage.removeItem("geifem_empresa_id");
  }, []);

  const recargarEmpresas = useCallback(async () => {
    const { data } = await api.get("/api/configuracion/datos-empresa");
    setEmpresas(data);
    // Se sincroniza con la empresa guardada al iniciar sesión; si ya no es
    // accesible, se activa la primera disponible.
    const guardada = localStorage.getItem("geifem_empresa_id");
    cambiarEmpresa(data.some((e) => e.id === guardada) ? guardada : data[0]?.id || null);
    return data;
  }, [cambiarEmpresa]);

  useEffect(() => {
    if (!usuario) {
      setEmpresas([]);
      return;
    }
    recargarEmpresas().catch(() => setEmpresas([]));
  }, [usuario, recargarEmpresas]);

  const empresaActiva = empresas.find((e) => e.id === empresaId) || null;

  // Se recarga al cambiar de empresa o al editar sus datos (régimen, responsabilidades).
  useEffect(() => {
    if (!empresaId || !usuario) {
      setPerfil(null);
      return;
    }
    api
      .get("/api/configuracion/perfil-tributario", { headers: { "X-Empresa-Id": empresaId } })
      .then((r) => setPerfil(r.data))
      .catch(() => setPerfil(null));
  }, [empresaId, usuario, empresaActiva]);

  return (
    <EmpresaContext.Provider
      value={{ empresas, empresaId, empresaActiva, perfil, cambiarEmpresa, recargarEmpresas }}
    >
      {children}
    </EmpresaContext.Provider>
  );
}

export function useEmpresa() {
  const ctx = useContext(EmpresaContext);
  if (!ctx) throw new Error("useEmpresa fuera de EmpresaProvider");
  return ctx;
}
