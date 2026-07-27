import { useEffect, useState } from "react";
import api from "../core/api.js";
import Table from "../shared/layout/Table/index.jsx";
import Modal from "../shared/layout/Modal/index.jsx";
import FormField, { Input } from "../shared/layout/FormField/index.jsx";
import { useAuth } from "../shared/auth/AuthContext.jsx";

/**
 * CRUD genérico para recursos multi-tenant.
 * columns: [{key, label, render?}] — describe qué mostrar en la tabla.
 * fields:  [{key, label, type?, hint?}] — describe el formulario.
 */
export default function ResourceCrud({
  titulo,
  endpoint,
  modulo,
  columns,
  fields,
}) {
  const { puede } = useAuth();
  const [rows, setRows] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
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
      setError(err.response?.data?.detail || err.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint]);

  const abrirCrear = () => {
    setEditando(null);
    setForm({});
    setOpenForm(true);
  };
  const abrirEditar = (row) => {
    setEditando(row);
    setForm({ ...row });
    setOpenForm(true);
  };

  const guardar = async () => {
    try {
      if (editando) {
        await api.put(`${endpoint}/${editando.id}`, form);
      } else {
        await api.post(endpoint, form);
      }
      setOpenForm(false);
      cargar();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  const inactivar = async (row) => {
    if (!confirm(`¿Inactivar "${row.nombre || row.id}"?`)) return;
    await api.post(`${endpoint}/${row.id}/inactivar`);
    cargar();
  };

  const cols = [
    ...columns,
    {
      key: "_acciones",
      label: "Acciones",
      render: (r) => (
        <div className="flex gap-2">
          {puede(modulo, "editar") && (
            <button
              onClick={() => abrirEditar(r)}
              className="text-xs text-geifem-blue hover:underline"
            >
              Editar
            </button>
          )}
          {puede(modulo, "inactivar") && r.activo !== false && (
            <button
              onClick={() => inactivar(r)}
              className="text-xs text-red-600 hover:underline"
            >
              Inactivar
            </button>
          )}
          {r.activo === false && (
            <span className="text-xs text-slate-400">inactivo</span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">{titulo}</h1>
        {puede(modulo, "crear") && (
          <button
            onClick={abrirCrear}
            className="bg-geifem-navy text-white text-sm px-4 py-2 rounded hover:bg-geifem-blue"
          >
            + Nuevo
          </button>
        )}
      </div>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {cargando ? (
        <div className="text-slate-500">Cargando…</div>
      ) : (
        <Table columns={cols} rows={rows} />
      )}

      <Modal
        open={openForm}
        onClose={() => setOpenForm(false)}
        title={editando ? `Editar ${titulo}` : `Nuevo — ${titulo}`}
        footer={
          <>
            <button
              onClick={() => setOpenForm(false)}
              className="px-3 py-1.5 rounded border border-slate-300 text-sm"
            >
              Cancelar
            </button>
            <button
              onClick={guardar}
              className="px-3 py-1.5 rounded bg-geifem-navy text-white text-sm"
            >
              Guardar
            </button>
          </>
        }
      >
        {fields.map((f) => (
          <FormField key={f.key} label={f.label} hint={f.hint}>
            <Input
              type={f.type || "text"}
              value={form[f.key] ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  [f.key]:
                    f.type === "number"
                      ? e.target.value === ""
                        ? ""
                        : Number(e.target.value)
                      : e.target.value,
                })
              }
            />
          </FormField>
        ))}
      </Modal>
    </div>
  );
}
