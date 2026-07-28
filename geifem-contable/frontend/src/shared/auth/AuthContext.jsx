import { createContext, useContext, useEffect, useState } from "react";
import api from "../../core/api.js";

const AuthContext = createContext(null);

// Usuario demo provisional para revisar la interfaz cuando el backend
// FastAPI no está disponible (por ejemplo, en la preview sin uvicorn corriendo).
const DEMO_EMAIL = "demo@geifem.co";
const DEMO_PASSWORD = "demo1234";
const DEMO_TOKEN = "demo-token-local";
const DEMO_EMPRESA_ID = "demo-empresa";
const DEMO_USER = {
  email: DEMO_EMAIL,
  nombre: "Usuario Demo",
  rol: "admin",
  empresa_ids: [DEMO_EMPRESA_ID],
  permisos: {},
  activo: true,
};

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("geifem_token");
    if (!token) {
      setCargando(false);
      return;
    }
    if (token === DEMO_TOKEN) {
      setUsuario(DEMO_USER);
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
    // Intento contra backend real
    try {
      const { data } = await api.post("/api/auth/login", { email, password });
      localStorage.setItem("geifem_token", data.access_token);
      if (data.empresa_activa_id) {
        localStorage.setItem("geifem_empresa_id", data.empresa_activa_id);
      }
      setUsuario(data.usuario);
      return data;
    } catch (err) {
      // Fallback demo si backend no responde o credenciales demo válidas
      const backendCaido = !err.response;
      const esDemo = email === DEMO_EMAIL && password === DEMO_PASSWORD;
      if (esDemo && (backendCaido || err.response?.status === 401)) {
        localStorage.setItem("geifem_token", DEMO_TOKEN);
        localStorage.setItem("geifem_empresa_id", DEMO_EMPRESA_ID);
        setUsuario(DEMO_USER);
        return { access_token: DEMO_TOKEN, usuario: DEMO_USER };
      }
      throw err;
    }
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

