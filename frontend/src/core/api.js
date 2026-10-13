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
  (r) => {
    // El documento quedó como solicitud pendiente de aprobación: no se creó todavía.
    if (r.status === 202 && r.data?.por_aprobar) {
      const err = new Error(r.data.detail);
      err.response = { status: 202, data: { detail: r.data.detail, por_aprobar: true } };
      err.porAprobar = true;
      window.dispatchEvent(new CustomEvent("aprobaciones:cambio"));
      return Promise.reject(err);
    }
    return r;
  },
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
