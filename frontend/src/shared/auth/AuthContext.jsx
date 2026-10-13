import { createContext, useContext, useEffect, useState } from "react";
import api from "../../core/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  // La cookie httpOnly no es legible desde JS: se pregunta al backend si hay sesión.
  useEffect(() => {
    api
      .get("/api/auth/me")
      .then((r) => setUsuario(r.data))
      .catch(() => setUsuario(null))
      .finally(() => setCargando(false));
  }, []);

  const iniciarSesion = (data) => {
    if (data.empresa_activa_id) {
      localStorage.setItem("geifem_empresa_id", data.empresa_activa_id);
    }
    setUsuario(data.usuario);
    return data;
  };

  const login = async (email, password) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    return iniciarSesion(data);
  };

  const registro = async (payload) => {
    const { data } = await api.post("/api/auth/registro", payload);
    return iniciarSesion(data);
  };

  const logout = async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      localStorage.removeItem("geifem_empresa_id");
      setUsuario(null);
    }
  };

  const refrescarUsuario = async () => {
    const { data } = await api.get("/api/auth/me");
    setUsuario(data);
    return data;
  };

  const puede = (modulo, accion) =>
    Boolean(usuario) && (usuario.permisos?.[modulo] || []).includes(accion);

  return (
    <AuthContext.Provider
      value={{ usuario, cargando, login, registro, logout, refrescarUsuario, puede }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
