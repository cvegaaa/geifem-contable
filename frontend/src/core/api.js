import axios from "axios";

// Mismo origen: en desarrollo lo resuelve el proxy de Vite y en producción nginx.
// La sesión viaja en una cookie httpOnly; aquí solo se agrega la empresa activa.
const api = axios.create({ withCredentials: true });

api.interceptors.request.use((config) => {
  const empresaId = localStorage.getItem("geifem_empresa_id");
  if (empresaId) config.headers["X-Empresa-Id"] = empresaId;
  return config;
});

// FastAPI responde los errores de validación (422) como lista; se convierten
// a texto para que todas las pantallas puedan mostrar `detail` directamente.
function normalizarDetalle(err) {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    err.response.data.detail = detail
      .map((d) => `${(d.loc || []).filter((x) => x !== "body").join(".")}: ${d.msg}`)
      .join(" · ");
  }
}

api.interceptors.response.use(
  (r) => r,
  (err) => {
    normalizarDetalle(err);
    const url = err.config?.url || "";
    const esAuth = url.startsWith("/api/auth/");
    if (err.response?.status === 401 && !esAuth && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;
