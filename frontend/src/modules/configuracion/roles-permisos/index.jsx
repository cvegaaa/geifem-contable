import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

const MODULOS = {
  configuracion: "Configuración", contabilidad: "Contabilidad", facturacion: "Facturación", inventario: "Inventario",
  compras: "Compras", tesoreria: "Tesorería", nomina: "Nómina", reportes: "Reportes",
};
const ACCIONES = { leer: "Ver", crear: "Crear", editar: "Editar", inactivar: "Anular", aprobar: "Aprobar" };

const vacio = () => ({ clave: null, nombre: "", permisos: Object.fromEntries(Object.keys(MODULOS).map((m) => [m, []])), requiere_aprobacion: false });

export default function Page() {
  const { usuario, puede, refrescarUsuario } = useAuth();
  const esAdmin = usuario?.rol === "admin";
  const [roles, setRoles] = useState([]);
  const [edicion, setEdicion] = useState(null);
  const [error, setError] = useState(null);
  const [errorModal, setErrorModal] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/configuracion/roles");
      setRoles(data.roles);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); }, []);

  const alternar = (modulo, accion) =>
    setEdicion((e) => {
      const actual = new Set(e.permisos[modulo] || []);
      if (actual.has(accion)) actual.delete(accion);
      else actual.add(accion);
      // Crear, editar, anular o aprobar sin poder ver no tiene sentido.
      if (accion !== "leer" && actual.has(accion)) actual.add("leer");
      if (accion === "leer" && !actual.has("leer")) actual.clear();
      return { ...e, permisos: { ...e.permisos, [modulo]: [...actual] } };
    });

  const guardar = async () => {
    setErrorModal(null);
    const cuerpo = { nombre: edicion.nombre, permisos: edicion.permisos, requiere_aprobacion: edicion.requiere_aprobacion };
    try {
      if (edicion.clave) await api.put(`/api/configuracion/roles/${edicion.clave}`, cuerpo);
      else await api.post("/api/configuracion/roles", cuerpo);
      setMensaje(`Rol «${edicion.nombre}» guardado. Los cambios aplican de inmediato a sus usuarios.`);
      setEdicion(null);
      cargar();
      refrescarUsuario().catch(() => {});
    } catch (e) {
      setErrorModal(mensajeError(e));
    }
  };

  const eliminar = async (r) => {
    if (!window.confirm(`¿Eliminar el rol «${r.nombre}»?`)) return;
    try {
      await api.delete(`/api/configuracion/roles/${r.clave}`);
      setMensaje(`Rol «${r.nombre}» eliminado`);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  const resumen = (r) =>
    Object.entries(MODULOS).filter(([m]) => (r.permisos[m] || []).length)
      .map(([m, n]) => `${n}: ${(r.permisos[m] || []).map((a) => ACCIONES[a]).join("/")}`).join(" · ");

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Roles y permisos</h1>
        {esAdmin && (
          <button onClick={() => { setEdicion(vacio()); setErrorModal(null); }} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">+ Nuevo rol</button>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-4">
        El acceso de cada usuario depende de su rol: aquí defines qué puede ver, crear, editar, anular y aprobar en cada módulo. Los cambios aplican de inmediato
        a todos los usuarios del rol. Un rol puede exigir <b>aprobación</b>: lo que sus usuarios registren queda pendiente hasta que quien tenga el permiso «Aprobar» lo autorice.
      </p>
      <Avisos error={error} mensaje={mensaje} />
      <div className="space-y-3">
        {roles.map((r) => (
          <section key={r.clave} className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-semibold text-geifem-navy">
                  {r.nombre}
                  {r.sistema && <span className="ml-2 text-[11px] text-slate-500 font-normal">rol base</span>}
                  {r.requiere_aprobacion && <span className="ml-2 text-[11px] bg-amber-50 text-amber-700 rounded-sm px-1.5 py-0.5 font-normal">requiere aprobación</span>}
                </h2>
                <p className="text-xs text-slate-500">{r.usuarios} usuario(s)</p>
              </div>
              {esAdmin && (
                <div className="flex gap-3 text-sm">
                  {r.clave === "admin" ? <span className="text-xs text-slate-400">Todos los permisos (no se modifica)</span> : (
                    <button onClick={() => { setEdicion({ ...JSON.parse(JSON.stringify(r)) }); setErrorModal(null); }} className="text-geifem-blue hover:underline">Editar permisos</button>
                  )}
                  {!r.sistema && <button onClick={() => eliminar(r)} className="text-red-600 hover:underline">Eliminar</button>}
                </div>
              )}
            </div>
            <p className="text-xs text-slate-600 mt-2">{r.clave === "admin" ? "Acceso total a todos los módulos." : resumen(r) || "Sin acceso a ningún módulo."}</p>
          </section>
        ))}
      </div>
      {!puede("configuracion", "leer") && <p className="text-sm text-red-600">No tienes acceso a esta pantalla.</p>}

      <Modal
        open={Boolean(edicion)} onClose={() => setEdicion(null)} ancho="max-w-3xl"
        title={edicion ? (edicion.clave ? `Permisos del rol ${edicion.nombre}` : "Nuevo rol") : ""}
        footer={<>
          <button onClick={() => setEdicion(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={guardar} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Guardar rol</button>
        </>}
      >
        {edicion && (
          <>
            <FormField label="Nombre del rol">
              <Input value={edicion.nombre} disabled={Boolean(edicion.sistema)} onChange={(e) => setEdicion({ ...edicion, nombre: e.target.value })} />
            </FormField>
            <label className="flex items-center gap-2 text-sm mb-3">
              <input type="checkbox" checked={edicion.requiere_aprobacion} onChange={(e) => setEdicion({ ...edicion, requiere_aprobacion: e.target.checked })} />
              Lo que registren sus usuarios requiere aprobación
            </label>
            <div className="border border-slate-200 rounded-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-100">
                  <tr><th className="text-left px-3 py-1.5">Módulo</th>{Object.values(ACCIONES).map((n) => <th key={n} className="px-2 py-1.5">{n}</th>)}</tr>
                </thead>
                <tbody>
                  {Object.entries(MODULOS).map(([m, n]) => (
                    <tr key={m} className="border-t border-slate-100">
                      <td className="px-3 py-1">{n}</td>
                      {Object.keys(ACCIONES).map((a) => (
                        <td key={a} className="text-center">
                          <input type="checkbox" checked={(edicion.permisos[m] || []).includes(a)} onChange={() => alternar(m, a)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 mt-2">«Aprobar» permite autorizar o rechazar los documentos de ese módulo que registren los usuarios que requieren aprobación.</p>
            {errorModal && <p className="text-sm text-red-600 mt-2">{errorModal}</p>}
          </>
        )}
      </Modal>
    </div>
  );
}
