import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";
import FormField, { Input } from "../layout/FormField/index.jsx";
import EmpresaForm, { EMPRESA_VACIA, empresaParaEnviar } from "../empresa/EmpresaForm.jsx";

export default function LoginPage() {
  const { usuario, login, registro } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [modo, setModo] = useState("login"); // login | registro
  const [cuenta, setCuenta] = useState({ nombre: "", email: "", password: "" });
  const [empresa, setEmpresa] = useState(EMPRESA_VACIA);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  const setC = (campo, v) => setCuenta((c) => ({ ...c, [campo]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      if (modo === "login") {
        await login(cuenta.email, cuenta.password);
      } else {
        await registro({ ...cuenta, empresa: empresaParaEnviar(empresa) });
      }
      navigate(location.state?.from?.pathname || "/", { replace: true });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          (err.response ? "No se pudo completar la operación" : "No hay conexión con el servidor")
      );
    } finally {
      setCargando(false);
    }
  };

  const esRegistro = modo === "registro";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4 py-8">
      <form
        onSubmit={submit}
        className={`w-full ${esRegistro ? "max-w-xl" : "max-w-sm"} bg-white rounded-xl shadow-lg p-8 border-t-4 border-geifem-gold`}
      >
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-geifem-navy">GEIFEM</h1>
          <p className="text-xs text-slate-500 uppercase tracking-wide">
            Gestión Integral para el Fortalecimiento Empresarial
          </p>
        </div>

        {esRegistro && (
          <FormField label="Tu nombre">
            <Input required value={cuenta.nombre} onChange={(e) => setC("nombre", e.target.value)} />
          </FormField>
        )}
        <FormField label="Email">
          <Input
            type="email"
            required
            autoComplete="email"
            value={cuenta.email}
            onChange={(e) => setC("email", e.target.value)}
          />
        </FormField>
        <FormField label="Contraseña" hint={esRegistro ? "Mínimo 8 caracteres" : undefined}>
          <Input
            type="password"
            required
            minLength={esRegistro ? 8 : undefined}
            autoComplete={esRegistro ? "new-password" : "current-password"}
            value={cuenta.password}
            onChange={(e) => setC("password", e.target.value)}
          />
        </FormField>

        {esRegistro && (
          <fieldset className="mt-2 mb-2 border-t border-slate-200 pt-4">
            <legend className="text-sm font-semibold text-geifem-navy px-1">Datos de tu empresa</legend>
            <EmpresaForm value={empresa} onChange={setEmpresa} />
          </fieldset>
        )}

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          type="submit"
          disabled={cargando}
          className="w-full bg-geifem-navy text-white font-semibold py-2 rounded-md hover:bg-geifem-blue transition disabled:opacity-60"
        >
          {cargando ? "Procesando…" : esRegistro ? "Crear cuenta" : "Ingresar"}
        </button>
        <button
          type="button"
          onClick={() => {
            setModo(esRegistro ? "login" : "registro");
            setError(null);
          }}
          className="w-full mt-3 text-sm text-geifem-blue hover:underline"
        >
          {esRegistro ? "Ya tengo cuenta: ingresar" : "¿No tienes cuenta? Crea una con tu empresa"}
        </button>
      </form>
    </div>
  );
}
