import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      await login(email, password);
      const to = location.state?.from?.pathname || "/";
      navigate(to, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo iniciar sesión");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-white rounded-xl shadow-lg p-8 border-t-4 border-geifem-gold"
      >
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-geifem-navy">GEIFEM</h1>
          <p className="text-xs text-slate-500 uppercase tracking-wide">
            Gestión Integral para el Fortalecimiento Empresarial
          </p>
        </div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
        <input
          type="email"
          required
          className="w-full border border-slate-300 rounded-md px-3 py-2 mb-4 focus:ring-2 focus:ring-geifem-blue focus:outline-none"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
        <input
          type="password"
          required
          className="w-full border border-slate-300 rounded-md px-3 py-2 mb-4 focus:ring-2 focus:ring-geifem-blue focus:outline-none"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <p className="text-xs text-slate-500 mb-3 bg-slate-50 border border-slate-200 rounded p-2">
          <strong>Acceso demo:</strong> demo@geifem.co / demo1234
        </p>
        <button
          type="submit"
          disabled={cargando}
          className="w-full bg-geifem-navy text-white font-semibold py-2 rounded-md hover:bg-geifem-blue transition disabled:opacity-60"
        >
          {cargando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
