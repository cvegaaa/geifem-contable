import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

const FORM_NUEVO = { nombre: "", email: "", password: "", rol: "vendedor", empresa_ids: [], activo: true };

export default function Page() {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "admin";
  const [usuarios, setUsuarios] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [roles, setRoles] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [nuevo, setNuevo] = useState(null);      // formulario de alta
  const [edicion, setEdicion] = useState(null);  // usuario en edición
  const [clave, setClave] = useState(null);      // usuario al que se le restablece la contraseña
  const [claveNueva, setClaveNueva] = useState("");
  const [errorModal, setErrorModal] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = async () => {
    try {
      const [us, emp, rl] = await Promise.all([
        api.get("/api/configuracion/usuarios-roles"),
        api.get("/api/configuracion/datos-empresa").catch(() => ({ data: [] })),
        api.get("/api/configuracion/roles").catch(() => ({ data: { roles: [] } })),
      ]);
      setUsuarios(us.data);
      setEmpresas(emp.data || []);
      setRoles(rl.data.roles || []);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); }, []);

  const crear = async () => {
    setErrorModal(null);
    if (!nuevo.nombre.trim()) return setErrorModal("El nombre es obligatorio");
    if (!nuevo.email.trim()) return setErrorModal("El email es obligatorio");
    if (nuevo.password.length < 8) return setErrorModal("La contraseña debe tener al menos 8 caracteres");
    setGuardando(true);
    try {
      await api.post("/api/configuracion/usuarios-roles", { ...nuevo });
      setMensaje(`Usuario ${nuevo.email} creado`);
      setNuevo(null);
      cargar();
    } catch (e) {
      setErrorModal(mensajeError(e));
    } finally {
      setGuardando(false);
    }
  };

  const abrirEdicion = (u) => {
    setErrorModal(null);
    setEdicion({ ...u });
  };

  const rolDe = (clave) => roles.find((r) => r.clave === clave);

  const guardarEdicion = async () => {
    setErrorModal(null);
    setGuardando(true);
    try {
      await api.put(`/api/configuracion/usuarios-roles/${edicion.id}`, {
        nombre: edicion.nombre, rol: edicion.rol, activo: edicion.activo,
        empresa_ids: edicion.empresa_ids,
        requiere_aprobacion: edicion.requiere_aprobacion ?? null,
      });
      setMensaje(`Usuario ${edicion.email} actualizado. Si cambiaste su rol, su sesión se cerró.`);
      setEdicion(null);
      cargar();
    } catch (e) {
      setErrorModal(mensajeError(e));
    } finally {
      setGuardando(false);
    }
  };

  const restablecer = async () => {
    setErrorModal(null);
    if (claveNueva.length < 8) return setErrorModal("La contraseña debe tener al menos 8 caracteres");
    try {
      await api.post(`/api/configuracion/usuarios-roles/${clave.id}/restablecer-password`, { nueva: claveNueva });
      setMensaje(`Contraseña de ${clave.email} restablecida. Comunícasela de forma segura; sus sesiones abiertas se cerraron.`);
      setClave(null);
      setClaveNueva("");
    } catch (e) {
      setErrorModal(mensajeError(e));
    }
  };

  const toggleEmpresa = (setter, id) =>
    setter((f) => ({ ...f, empresa_ids: f.empresa_ids.includes(id) ? f.empresa_ids.filter((x) => x !== id) : [...f.empresa_ids, id] }));

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Usuarios</h1>
        {esAdmin && (
          <button onClick={() => { setNuevo({ ...FORM_NUEVO }); setErrorModal(null); }} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">
            + Nuevo usuario
          </button>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-3">
        Cada usuario tiene un rol y su acceso a los módulos es el de ese rol. Los permisos de cada rol se definen en{" "}
        <Link to="/configuracion/roles-permisos" className="text-geifem-blue hover:underline">Roles y permisos</Link>.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      <Table
        columns={[
          { key: "nombre", label: "Nombre" },
          { key: "email", label: "Email" },
          { key: "rol_nombre", label: "Rol", render: (r) => r.rol_nombre || r.rol },
          { key: "aprobacion_requerida", label: "Aprobación", render: (r) => (r.aprobacion_requerida ? "Requiere" : "—") },
          { key: "activo", label: "Estado", render: (r) => (r.activo ? "Activo" : <span className="text-red-600">Inactivo</span>) },
          {
            key: "_acciones", label: "",
            render: (r) => esAdmin && (
              <div className="flex gap-3 whitespace-nowrap">
                <button onClick={() => abrirEdicion(r)} className="text-xs text-geifem-blue hover:underline">Editar</button>
                <button onClick={() => { setClave(r); setClaveNueva(""); setErrorModal(null); }} className="text-xs text-slate-600 hover:underline">Restablecer contraseña</button>
              </div>
            ),
          },
        ]}
        rows={usuarios}
        empty="Sin usuarios registrados"
      />

      {/* Alta */}
      <Modal
        open={Boolean(nuevo)} onClose={() => setNuevo(null)} title="Nuevo usuario"
        footer={<>
          <button onClick={() => setNuevo(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={crear} disabled={guardando} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white disabled:opacity-50">{guardando ? "Creando…" : "Crear usuario"}</button>
        </>}
      >
        {nuevo && (
          <>
            <FormField label="Nombre completo"><Input value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} /></FormField>
            <FormField label="Email"><Input type="email" value={nuevo.email} onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })} /></FormField>
            <FormField label="Contraseña" hint="Mínimo 8 caracteres"><Input type="password" value={nuevo.password} onChange={(e) => setNuevo({ ...nuevo, password: e.target.value })} /></FormField>
            <FormField label="Rol" hint="Sus permisos son los del rol; se editan en Roles y permisos.">
              <Select value={nuevo.rol} onChange={(e) => setNuevo({ ...nuevo, rol: e.target.value })}>{roles.map((r) => <option key={r.clave} value={r.clave}>{r.nombre}</option>)}</Select>
            </FormField>
            {empresas.length > 1 && (
              <FormField label="Empresas asignadas" hint="Sin selección = solo la empresa activa">
                <div className="max-h-32 overflow-auto border border-slate-200 rounded-sm p-2 space-y-1">
                  {empresas.map((e) => (
                    <label key={e.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={nuevo.empresa_ids.includes(e.id)} onChange={() => toggleEmpresa(setNuevo, e.id)} />
                      {e.razon_social}
                    </label>
                  ))}
                </div>
              </FormField>
            )}
            {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
          </>
        )}
      </Modal>

      {/* Edición */}
      <Modal
        open={Boolean(edicion)} onClose={() => setEdicion(null)} title={edicion ? `Editar a ${edicion.email}` : ""} ancho="max-w-2xl"
        footer={<>
          <button onClick={() => setEdicion(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={guardarEdicion} disabled={guardando} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white disabled:opacity-50">{guardando ? "Guardando…" : "Guardar cambios"}</button>
        </>}
      >
        {edicion && (
          <>
            <div className="grid grid-cols-2 gap-x-3">
              <FormField label="Nombre"><Input value={edicion.nombre} onChange={(e) => setEdicion({ ...edicion, nombre: e.target.value })} /></FormField>
              <FormField label="Rol" hint="Su acceso es el del rol.">
                <Select value={edicion.rol} onChange={(e) => setEdicion({ ...edicion, rol: e.target.value })}>{roles.map((r) => <option key={r.clave} value={r.clave}>{r.nombre}</option>)}</Select>
              </FormField>
            </div>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input type="checkbox" checked={edicion.activo} onChange={(e) => setEdicion({ ...edicion, activo: e.target.checked })} />
              Usuario activo (si lo desactivas, no podrá ingresar)
            </label>
            <label className="flex items-center gap-2 text-sm mb-1">
              <input type="checkbox"
                checked={edicion.requiere_aprobacion ?? Boolean(rolDe(edicion.rol)?.requiere_aprobacion)}
                onChange={(e) => setEdicion({ ...edicion, requiere_aprobacion: e.target.checked })} />
              Lo que registre este usuario requiere aprobación
            </label>
            <p className="text-xs text-slate-500 mb-3">
              Por defecto sigue lo que define su rol ({rolDe(edicion.rol)?.requiere_aprobacion ? "requiere aprobación" : "no requiere aprobación"}).
              Aprueba quien tenga el permiso «Aprobar» en el módulo.
            </p>
            {rolDe(edicion.rol) && (
              <p className="text-xs text-slate-600 mb-3 bg-slate-50 border border-slate-200 rounded-sm px-2 py-1.5">
                Acceso por rol: {Object.entries(rolDe(edicion.rol).permisos).filter(([, a]) => a.length).map(([m, a]) => `${m} (${a.join(", ")})`).join(" · ") || "ninguno"}.
              </p>
            )}
            {empresas.length > 1 && (
              <FormField label="Empresas">
                <div className="max-h-28 overflow-auto border border-slate-200 rounded-sm p-2 space-y-1">
                  {empresas.map((e) => (
                    <label key={e.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={edicion.empresa_ids.includes(e.id)} onChange={() => toggleEmpresa(setEdicion, e.id)} />
                      {e.razon_social}
                    </label>
                  ))}
                </div>
              </FormField>
            )}
            {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
          </>
        )}
      </Modal>

      {/* Restablecer contraseña */}
      <Modal
        open={Boolean(clave)} onClose={() => setClave(null)} title={clave ? `Restablecer contraseña de ${clave.email}` : ""}
        footer={<>
          <button onClick={() => setClave(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={restablecer} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Restablecer</button>
        </>}
      >
        <p className="text-sm text-slate-600 mb-3">Defines una contraseña nueva y se la comunicas al usuario. Sus sesiones abiertas se cerrarán.</p>
        <FormField label="Contraseña nueva" hint="Mínimo 8 caracteres"><Input type="password" value={claveNueva} onChange={(e) => setClaveNueva(e.target.value)} /></FormField>
        {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
      </Modal>
    </div>
  );
}
