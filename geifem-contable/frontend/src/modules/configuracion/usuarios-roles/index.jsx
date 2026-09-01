import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const ROLES = [
  { valor: "admin", etiqueta: "Administrador" },
  { valor: "contador", etiqueta: "Contador" },
  { valor: "vendedor", etiqueta: "Vendedor" },
];

export default function Page() {
  const [usuarios, setUsuarios] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [plantillas, setPlantillas] = useState({});
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [form, setForm] = useState({
    nombre: "",
    email: "",
    password: "",
    rol: "vendedor",
    empresa_ids: [],
    activo: true,
  });

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
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const set = (campo, valor) => setForm((f) => ({ ...f, [campo]: valor }));

  const toggleEmpresa = (id) =>
    setForm((f) => ({
      ...f,
      empresa_ids: f.empresa_ids.includes(id)
        ? f.empresa_ids.filter((x) => x !== id)
        : [...f.empresa_ids, id],
    }));

  const crear = async () => {
    setError(null);
    setMensaje(null);
    if (!form.nombre.trim()) return setError("El nombre es obligatorio");
    if (!form.email.trim()) return setError("El email es obligatorio");
    if (form.password.length < 8) return setError("La contraseña debe tener al menos 8 caracteres");

    setGuardando(true);
    try {
      await api.post("/api/configuracion/usuarios-roles", {
        nombre: form.nombre,
        email: form.email,
        password: form.password,
        rol: form.rol,
        empresa_ids: form.empresa_ids,
        activo: form.activo,
        permisos: {},
      });
      setMensaje(`Usuario ${form.email} creado`);
      setAbierto(false);
      setForm({ nombre: "", email: "", password: "", rol: "vendedor", empresa_ids: [], activo: true });
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setGuardando(false);
    }
  };

  const permisosRol = plantillas[form.rol] || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">Usuarios y roles</h1>
        <button
          onClick={() => setAbierto(true)}
          className="text-sm px-4 py-2 rounded bg-geifem-navy text-white hover:bg-geifem-blue"
        >
          + Nuevo usuario
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">{mensaje}</div>}

      <Table
        columns={[
          { key: "nombre", label: "Nombre" },
          { key: "email", label: "Email" },
          { key: "rol", label: "Rol", render: (r) => ROLES.find((x) => x.valor === r.rol)?.etiqueta || r.rol },
          { key: "empresa_ids", label: "Empresas", render: (r) => (r.empresa_ids?.length ?? 0) || "Todas" },
          { key: "activo", label: "Activo", render: (r) => (r.activo ? "Sí" : "No") },
        ]}
        rows={usuarios}
        empty="Sin usuarios registrados"
      />

      <Modal
        open={abierto}
        onClose={() => setAbierto(false)}
        title="Nuevo usuario"
        footer={
          <>
            <button onClick={() => setAbierto(false)} className="px-3 py-1.5 text-sm rounded border border-slate-300">
              Cancelar
            </button>
            <button
              onClick={crear}
              disabled={guardando}
              className="px-4 py-1.5 text-sm rounded bg-geifem-navy text-white disabled:opacity-50"
            >
              {guardando ? "Creando…" : "Crear usuario"}
            </button>
          </>
        }
      >
        <FormField label="Nombre completo">
          <Input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} />
        </FormField>
        <FormField label="Email">
          <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </FormField>
        <FormField label="Contraseña" hint="Mínimo 8 caracteres">
          <Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} />
        </FormField>
        <FormField label="Rol">
          <Select value={form.rol} onChange={(e) => set("rol", e.target.value)}>
            {ROLES.map((r) => (
              <option key={r.valor} value={r.valor}>{r.etiqueta}</option>
            ))}
          </Select>
        </FormField>

        {Object.keys(permisosRol).length > 0 && (
          <div className="mb-3 text-xs bg-slate-50 border border-slate-200 rounded p-3">
            <p className="font-semibold text-slate-600 mb-1">Permisos del rol</p>
            <ul className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-slate-600">
              {Object.entries(permisosRol).map(([modulo, acciones]) => (
                <li key={modulo}>
                  <span className="font-medium">{modulo}:</span> {(acciones || []).join(", ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        {empresas.length > 0 && (
          <FormField label="Empresas asignadas" hint="Sin selección = acceso a todas">
            <div className="max-h-32 overflow-auto border border-slate-200 rounded p-2 space-y-1">
              {empresas.map((e) => (
                <label key={e.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.empresa_ids.includes(e.id)}
                    onChange={() => toggleEmpresa(e.id)}
                  />
                  {e.razon_social || e.nombre || e.id}
                </label>
              ))}
            </div>
          </FormField>
        )}

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={form.activo} onChange={(e) => set("activo", e.target.checked)} />
          Usuario activo
        </label>
      </Modal>
    </div>
  );
}
