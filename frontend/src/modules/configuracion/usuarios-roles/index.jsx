import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

const ROLES = [
  { valor: "admin", etiqueta: "Administrador" },
  { valor: "contador", etiqueta: "Contador" },
  { valor: "auxiliar", etiqueta: "Auxiliar contable (requiere aprobación)" },
  { valor: "vendedor", etiqueta: "Vendedor" },
];
const MODULOS = [
  ["configuracion", "Configuración"], ["contabilidad", "Contabilidad"], ["facturacion", "Facturación"], ["inventario", "Inventario"],
  ["compras", "Compras"], ["tesoreria", "Tesorería"], ["nomina", "Nómina"], ["reportes", "Reportes"],
];
const ACCIONES = [["leer", "Ver"], ["crear", "Crear"], ["editar", "Editar"], ["inactivar", "Anular"], ["aprobar", "Aprobar"]];

const FORM_NUEVO = { nombre: "", email: "", password: "", rol: "vendedor", empresa_ids: [], activo: true };

export default function Page() {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "admin";
  const [usuarios, setUsuarios] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [plantillas, setPlantillas] = useState({});
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
      const [us, emp, pl] = await Promise.all([
        api.get("/api/configuracion/usuarios-roles"),
        api.get("/api/configuracion/datos-empresa").catch(() => ({ data: [] })),
        api.get("/api/configuracion/usuarios-roles/roles-plantilla").catch(() => ({ data: {} })),
      ]);
      setUsuarios(us.data);
      setEmpresas(emp.data || []);
      setPlantillas(pl.data || {});
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
      await api.post("/api/configuracion/usuarios-roles", { ...nuevo, permisos: {} });
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
    setEdicion({ ...u, permisos: JSON.parse(JSON.stringify(u.permisos || {})) });
  };

  const cambiarRol = (rol) =>
    setEdicion((e) => ({ ...e, rol, permisos: JSON.parse(JSON.stringify(plantillas[rol] || {})) }));

  const alternar = (modulo, accion) =>
    setEdicion((e) => {
      const actual = new Set(e.permisos[modulo] || []);
      if (actual.has(accion)) actual.delete(accion);
      else actual.add(accion);
      // Crear, editar o anular sin poder ver no tiene sentido.
      if (accion !== "leer" && actual.has(accion)) actual.add("leer");
      if (accion === "leer" && !actual.has("leer")) actual.clear();
      return { ...e, permisos: { ...e.permisos, [modulo]: [...actual] } };
    });

  const guardarEdicion = async () => {
    setErrorModal(null);
    setGuardando(true);
    try {
      await api.put(`/api/configuracion/usuarios-roles/${edicion.id}`, {
        nombre: edicion.nombre, rol: edicion.rol, activo: edicion.activo,
        permisos: edicion.permisos, empresa_ids: edicion.empresa_ids,
        requiere_aprobacion: edicion.requiere_aprobacion ?? null,
      });
      setMensaje(`Usuario ${edicion.email} actualizado. Si cambiaste su rol o permisos, su sesión se cerró.`);
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

  const resumenPermisos = (u) =>
    MODULOS.filter(([m]) => (u.permisos?.[m] || []).length).map(([m, n]) => `${n}${(u.permisos[m].length === 4 ? "" : ` (${u.permisos[m].join(", ")})`)}`).join(" · ");

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Usuarios y roles</h1>
        {esAdmin && (
          <button onClick={() => { setNuevo({ ...FORM_NUEVO }); setErrorModal(null); }} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">
            + Nuevo usuario
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      <Table
        columns={[
          { key: "nombre", label: "Nombre" },
          { key: "email", label: "Email" },
          { key: "rol", label: "Rol", render: (r) => ROLES.find((x) => x.valor === r.rol)?.etiqueta || r.rol },
          { key: "permisos", label: "Acceso a módulos", render: (r) => <span className="text-xs text-slate-500">{resumenPermisos(r)}</span> },
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
            <FormField label="Rol" hint="El rol define sus permisos iniciales; luego puedes ajustarlos módulo por módulo.">
              <Select value={nuevo.rol} onChange={(e) => setNuevo({ ...nuevo, rol: e.target.value })}>{ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}</Select>
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
              <FormField label="Rol" hint="Al cambiar de rol se aplica su plantilla de permisos.">
                <Select value={edicion.rol} onChange={(e) => cambiarRol(e.target.value)}>{ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}</Select>
              </FormField>
            </div>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input type="checkbox" checked={edicion.activo} onChange={(e) => setEdicion({ ...edicion, activo: e.target.checked })} />
              Usuario activo (si lo desactivas, no podrá ingresar)
            </label>
            <label className="flex items-center gap-2 text-sm mb-1">
              <input type="checkbox"
                checked={edicion.requiere_aprobacion ?? edicion.rol === "auxiliar"}
                onChange={(e) => setEdicion({ ...edicion, requiere_aprobacion: e.target.checked })} />
              Sus comprobantes requieren aprobación de un contador o administrador
            </label>
            <p className="text-xs text-slate-500 mb-3">«Aprobar» en Contabilidad permite autorizar los comprobantes de quienes requieren aprobación (administradores y contadores siempre pueden).</p>
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Permisos por módulo</h4>
            <div className="border border-slate-200 rounded-sm overflow-hidden mb-3">
              <table className="w-full text-sm">
                <thead className="bg-slate-100"><tr><th className="text-left px-3 py-1.5">Módulo</th>{ACCIONES.map(([, n]) => <th key={n} className="px-2 py-1.5">{n}</th>)}</tr></thead>
                <tbody>
                  {MODULOS.map(([m, n]) => (
                    <tr key={m} className="border-t border-slate-100">
                      <td className="px-3 py-1">{n}</td>
                      {ACCIONES.map(([a]) => (
                        <td key={a} className="text-center">
                          <input type="checkbox" checked={(edicion.permisos[m] || []).includes(a)} onChange={() => alternar(m, a)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
