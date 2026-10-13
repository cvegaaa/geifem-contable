import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useEmpresa } from "../../../core/EmpresaContext.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import EmpresaForm, { EMPRESA_VACIA, empresaParaEnviar } from "../../../shared/empresa/EmpresaForm.jsx";

export default function Page() {
  const { empresaActiva, recargarEmpresas, cambiarEmpresa } = useEmpresa();
  const { usuario, puede, refrescarUsuario } = useAuth();
  const [form, setForm] = useState(EMPRESA_VACIA);
  const [nueva, setNueva] = useState(EMPRESA_VACIA);
  const [abierto, setAbierto] = useState(false);
  const [mensaje, setMensaje] = useState(null);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!empresaActiva) return;
    // Empresas anteriores al perfil tributario: las opciones se derivan del régimen.
    const simple = empresaActiva.regimen_tributario === "SIMPLE";
    setForm({
      ...EMPRESA_VACIA,
      ...empresaActiva,
      agente_retenedor: empresaActiva.agente_retenedor ?? !simple,
      agente_reteiva: empresaActiva.agente_reteiva ?? (!simple && empresaActiva.responsable_iva !== false),
    });
  }, [empresaActiva]);

  const puedeEditar = puede("configuracion", "editar");
  const esAdmin = usuario?.rol === "admin";

  const guardar = async (e) => {
    e.preventDefault();
    setError(null);
    setMensaje(null);
    setGuardando(true);
    try {
      await api.put(`/api/configuracion/datos-empresa/${empresaActiva.id}`, empresaParaEnviar(form));
      await recargarEmpresas();
      setMensaje("Datos guardados. Los cambios de perfil tributario aplican a los documentos nuevos.");
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setGuardando(false);
    }
  };

  const crear = async () => {
    setError(null);
    setGuardando(true);
    try {
      const { data } = await api.post("/api/configuracion/datos-empresa", empresaParaEnviar(nueva));
      await refrescarUsuario();
      await recargarEmpresas();
      cambiarEmpresa(data.id);
      setAbierto(false);
      setNueva(EMPRESA_VACIA);
      setMensaje(`Empresa ${data.razon_social} creada y seleccionada`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Datos de empresa</h1>
        {esAdmin && (
          <button
            onClick={() => setAbierto(true)}
            className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue"
          >
            + Nueva empresa
          </button>
        )}
      </div>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-emerald-700">{mensaje}</div>}

      {empresaActiva ? (
        <form onSubmit={guardar} className="bg-white border border-slate-200 rounded-lg p-5">
          <EmpresaForm value={form} onChange={setForm} disabled={!puedeEditar} />
          {puedeEditar && (
            <button
              type="submit"
              disabled={guardando}
              className="mt-2 bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60"
            >
              {guardando ? "Guardando…" : "Guardar cambios"}
            </button>
          )}
        </form>
      ) : (
        <p className="text-slate-500">No hay una empresa seleccionada.</p>
      )}

      <Modal
        open={abierto}
        onClose={() => setAbierto(false)}
        title="Nueva empresa"
        footer={
          <>
            <button onClick={() => setAbierto(false)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">
              Cancelar
            </button>
            <button
              onClick={crear}
              disabled={guardando}
              className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm disabled:opacity-60"
            >
              Crear empresa
            </button>
          </>
        }
      >
        <p className="text-xs text-slate-500 mb-3">
          Se crea con el plan de cuentas base y la bodega principal.
        </p>
        <EmpresaForm value={nueva} onChange={setNueva} />
      </Modal>
    </div>
  );
}
