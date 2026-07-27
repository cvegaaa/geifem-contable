import { createContext, useContext, useEffect, useState } from "react";
import api from "../../core/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("geifem_token");
    if (!token) {
      setCargando(false);
      return;
    }
    api
      .get("/api/auth/me")
      .then((r) => setUsuario(r.data))
      .catch(() => localStorage.removeItem("geifem_token"))
      .finally(() => setCargando(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("geifem_token", data.access_token);
    if (data.empresa_activa_id) {
      localStorage.setItem("geifem_empresa_id", data.empresa_activa_id);
    }
    setUsuario(data.usuario);
    return data;
  };

  const logout = () => {
    localStorage.removeItem("geifem_token");
    localStorage.removeItem("geifem_empresa_id");
    setUsuario(null);
  };

  const puede = (modulo, accion) => {
    if (!usuario) return false;
    if (usuario.rol === "admin") return true;
    return (usuario.permisos?.[modulo] || []).includes(accion);
  };

  return (
    <AuthContext.Provider value={{ usuario, cargando, login, logout, puede }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
