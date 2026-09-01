import { useState } from "react";
import api from "../../core/api.js";
import FormField, { Input } from "../../shared/layout/FormField/index.jsx";

export default function ComprobanteForm({ tipo, titulo }) {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [descripcion, setDescripcion] = useState("");
  const [lineas, setLineas] = useState([
    { cuenta_puc_id: "", debito: 0, credito: 0, descripcion: "" },
  ]);
  const [mensaje, setMensaje] = useState(null);
  const [error, setError] = useState(null);

  const totalDeb = lineas.reduce((s, l) => s + Number(l.debito || 0), 0);
  const totalCre = lineas.reduce((s, l) => s + Number(l.credito || 0), 0);

  const actualizar = (i, campo, valor) => {
    const copia = [...lineas];
    copia[i][campo] = campo === "debito" || campo === "credito" ? Number(valor || 0) : valor;
    setLineas(copia);
  };

  const guardar = async (estado) => {
    setError(null);
    setMensaje(null);
    try {
      const { data } = await api.post("/api/contabilidad/comprobantes", {
        tipo,
        fecha,
        descripcion,
        lineas,
        estado,
      });
      setMensaje(`Guardado (consecutivo ${data.consecutivo}, estado ${data.estado})`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-4">{titulo}</h1>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Fecha">
          <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </FormField>
        <FormField label="Descripción">
          <Input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
        </FormField>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden mt-3">
        <table className="w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="text-left px-3 py-2">Cuenta PUC (id)</th>
              <th className="text-left px-3 py-2">Descripción</th>
              <th className="text-right px-3 py-2">Débito</th>
              <th className="text-right px-3 py-2">Crédito</th>
            </tr>
          </thead>
          <tbody>
            {lineas.map((l, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1">
                  <Input value={l.cuenta_puc_id} onChange={(e) => actualizar(i, "cuenta_puc_id", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Input value={l.descripcion} onChange={(e) => actualizar(i, "descripcion", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Input type="number" value={l.debito} onChange={(e) => actualizar(i, "debito", e.target.value)} />
                </td>
                <td className="px-2 py-1">
                  <Input type="number" value={l.credito} onChange={(e) => actualizar(i, "credito", e.target.value)} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50">
            <tr>
              <td colSpan={2} className="px-3 py-2 text-right font-semibold">Totales</td>
              <td className="px-3 py-2 text-right">{totalDeb.toFixed(2)}</td>
              <td className="px-3 py-2 text-right">{totalCre.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => setLineas([...lineas, { cuenta_puc_id: "", debito: 0, credito: 0, descripcion: "" }])}
          className="text-sm px-3 py-1.5 rounded border border-slate-300"
        >
          + Línea
        </button>
        <button
          onClick={() => guardar("borrador")}
          className="text-sm px-3 py-1.5 rounded bg-slate-200"
        >
          Guardar borrador
        </button>
        <button
          onClick={() => guardar("contabilizado")}
          disabled={Math.round(totalDeb * 100) !== Math.round(totalCre * 100)}
          className="text-sm px-3 py-1.5 rounded bg-geifem-navy text-white disabled:opacity-50"
        >
          Contabilizar
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-3 text-sm text-green-700">{mensaje}</p>}
    </div>
  );
}
