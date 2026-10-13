import { useEffect, useState } from "react";
import api from "../core/api.js";
import Table from "../shared/layout/Table/index.jsx";
import Modal from "../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../shared/layout/FormField/index.jsx";
import { useAuth } from "../shared/auth/AuthContext.jsx";
import { Avisos, mensajeError } from "../shared/documentos/index.jsx";
import { useEmpresa } from "../core/EmpresaContext.jsx";

/**
 * CRUD genérico para catálogos multiempresa.
 * columns: [{key, label, render?}]
 * fields:  [{key, label, type?, hint?, required?, options?, endpoint?, etiqueta?, defecto?}]
 *   type: "text" | "number" | "date" | "checkbox" | "select" (options fijas) | "ref" (opciones de otro endpoint)
 *         | "cuenta" (cuenta del PUC por código; `prefijos` filtra, `vacio` es el texto de la opción vacía)
 *   options: ["a", "b"] o [{valor, etiqueta}]
 *   mostrar: (perfil) => boolean — oculta el campo según el perfil tributario de la empresa.
 *   seccion: título de un grupo de campos (con `mostrar` opcional y `hint` texto o (perfil) => texto).
 * filtrar / ordenar: muestran solo algunas filas o en un orden propio (p. ej. el plan de cuentas por nivel).
 * extra: ({ recargar, avisar }) => nodo para acciones propias junto al botón "+ Nuevo".
 */
const normalizar = (options = []) =>
  options.map((o) => (typeof o === "string" ? { valor: o, etiqueta: o } : o));

function valoresIniciales(fields, respaldo = {}) {
  return Object.fromEntries(
    fields
      .filter((f) => f.defecto !== undefined || (f.defectoParametro && respaldo[f.defectoParametro]))
      .map((f) => [f.key, f.defecto !== undefined ? f.defecto : respaldo[f.defectoParametro]])
  );
}

export default function ResourceCrud({ titulo, endpoint, modulo, columns, fields: todosLosCampos, descripcion, extra, filtrar, ordenar }) {
  const { puede } = useAuth();
  const { perfil } = useEmpresa();
  // Los campos con `mostrar` solo aparecen si el perfil tributario de la empresa lo permite.
  const fields = todosLosCampos.filter((f) => !f.mostrar || (perfil && f.mostrar(perfil)));
  const [rows, setRows] = useState([]);
  const [refs, setRefs] = useState({});
  const [plan, setPlan] = useState([]);
  const [respaldo, setRespaldo] = useState({});   // cuentas de respaldo de la empresa (valor inicial de algunos campos)
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [errorForm, setErrorForm] = useState(null);
  const [openForm, setOpenForm] = useState(false);
  const [editando, setEditando] = useState(null);
  const [form, setForm] = useState({});

  const cargar = async () => {
    setCargando(true);
    setError(null);
    try {
      const { data } = await api.get(endpoint);
      setRows(data);
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    if (todosLosCampos.some((x) => x.defectoParametro)) {
      api.get("/api/configuracion/parametros-contables")
        .then((r) => setRespaldo(Object.fromEntries(r.data.map((p) => [p.clave, p.codigo]))))
        .catch(() => {});
    }
    if (todosLosCampos.some((x) => x.type === "cuenta")) {
      api.get("/api/configuracion/plan-cuentas").then((r) => setPlan(r.data)).catch(() => {});
    }
    for (const f of todosLosCampos.filter((x) => x.type === "ref")) {
      api.get(f.endpoint).then((r) => setRefs((prev) => ({ ...prev, [f.key]: r.data }))).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint]);

  const abrirCrear = () => {
    setEditando(null);
    setForm(valoresIniciales(fields, respaldo));
    setErrorForm(null);
    setOpenForm(true);
  };
  const abrirEditar = (row) => {
    setEditando(row);
    setForm({ ...row });
    setErrorForm(null);
    setOpenForm(true);
  };

  const guardar = async () => {
    const faltante = fields.find((f) => f.required && (form[f.key] === undefined || form[f.key] === ""));
    if (faltante) return setErrorForm(`Completa el campo «${faltante.label}»`);
    try {
      if (editando) await api.put(`${endpoint}/${editando.id}`, form);
      else await api.post(endpoint, form);
      setOpenForm(false);
      setMensaje(editando ? "Cambios guardados" : "Registro creado");
      cargar();
    } catch (err) {
      setErrorForm(mensajeError(err));
    }
  };

  const inactivar = async (row) => {
    if (!confirm(`¿Inactivar «${row.nombre || row.codigo || row.prefijo || "registro"}»? Dejará de aparecer en las listas.`)) return;
    try {
      await api.post(`${endpoint}/${row.id}/inactivar`);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const setCampo = (f, valor) => setForm((prev) => ({ ...prev, [f.key]: valor }));

  const control = (f) => {
    const valor = form[f.key];
    if (f.type === "checkbox") {
      return (
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={Boolean(valor)} onChange={(e) => setCampo(f, e.target.checked)} />
          {f.textoCheckbox || "Sí"}
        </label>
      );
    }
    if (f.type === "select" || f.type === "ref" || f.type === "cuenta") {
      let opciones;
      if (f.type === "select") opciones = normalizar(f.options);
      else if (f.type === "ref")
        opciones = (refs[f.key] || []).map((r) => ({ valor: r.id, etiqueta: f.etiqueta ? f.etiqueta(r) : r.nombre }));
      else
        opciones = plan
          .filter((c) => c.acepta_movimientos !== false && c.activo !== false)
          .filter((c) => !f.prefijos || f.prefijos.some((p) => c.codigo.startsWith(p)))
          .sort((a, b) => a.codigo.localeCompare(b.codigo))
          .map((c) => ({ valor: c.codigo, etiqueta: `${c.codigo} — ${c.nombre}` }));
      return (
        <Select value={valor ?? ""} onChange={(e) => setCampo(f, e.target.value || null)}>
          <option value="">{f.vacio || (f.required ? "Seleccionar…" : "—")}</option>
          {opciones.map((o) => (
            <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
          ))}
        </Select>
      );
    }
    return (
      <Input
        type={f.type || "text"}
        value={valor ?? ""}
        onChange={(e) =>
          setCampo(f, f.type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)
        }
      />
    );
  };

  const cols = [
    ...columns,
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <div className="flex gap-3 whitespace-nowrap">
          {puede(modulo, "editar") && r.activo !== false && (
            <button onClick={() => abrirEditar(r)} className="text-xs text-geifem-blue hover:underline">Editar</button>
          )}
          {puede(modulo, "inactivar") && r.activo !== false && (
            <button onClick={() => inactivar(r)} className="text-xs text-red-600 hover:underline">Inactivar</button>
          )}
          {r.activo === false && <span className="text-xs text-slate-400">inactivo</span>}
        </div>
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">{titulo}</h1>
        <div className="flex gap-2">
          {extra?.({ recargar: cargar, avisar: setMensaje })}
          {puede(modulo, "crear") && (
            <button onClick={abrirCrear} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
              + Nuevo
            </button>
          )}
        </div>
      </div>
      {descripcion ? <p className="text-sm text-slate-500 mb-4">{descripcion}</p> : <div className="mb-4" />}
      <Avisos error={error} mensaje={mensaje} />
      {cargando ? <div className="text-slate-500">Cargando…</div> : <Table columns={cols} rows={ordenar ? [...(filtrar ? rows.filter(filtrar) : rows)].sort(ordenar) : (filtrar ? rows.filter(filtrar) : rows)} />}

      <Modal
        open={openForm}
        onClose={() => setOpenForm(false)}
        title={editando ? `Editar — ${titulo}` : `Nuevo — ${titulo}`}
        footer={
          <>
            <button onClick={() => setOpenForm(false)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
            <button onClick={guardar} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Guardar</button>
          </>
        }
      >
        {fields.map((f) =>
          f.seccion ? (
            <div key={f.seccion} className="mt-4 mb-2 pt-3 border-t border-slate-200">
              <h4 className="text-sm font-semibold text-geifem-navy">{f.seccion}</h4>
              {f.hint && <p className="text-xs text-slate-500">{typeof f.hint === "function" ? f.hint(perfil) : f.hint}</p>}
            </div>
          ) : f.type === "checkbox" ? (
            <div key={f.key} className="mb-3">
              <span className="block text-sm font-medium text-slate-700 mb-1">{f.label}</span>
              {control(f)}
              {f.hint && <span className="block text-xs text-slate-500 mt-1">{f.hint}</span>}
            </div>
          ) : (
            <FormField key={f.key} label={f.required ? `${f.label} *` : f.label} hint={f.hint}>
              {control(f)}
            </FormField>
          )
        )}
        {errorForm && <p className="text-sm text-red-600">{errorForm}</p>}
      </Modal>
    </div>
  );
}

/** Muestra la etiqueta de una opción fija en las columnas de la tabla. */
export const etiquetaDe = (options, valor) =>
  normalizar(options).find((o) => o.valor === valor)?.etiqueta ?? valor ?? "";
