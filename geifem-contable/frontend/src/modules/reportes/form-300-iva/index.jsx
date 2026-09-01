import { useState } from "react";
import api from "../../../core/api.js";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

export default function Page() {
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const generar = async () => {
    setError(null);
    setData(null);
    try {
      const params = new URLSearchParams(rango);
      const { data } = await api.get(`/api/reportes/form-300-iva?${params}`);
      setData(data);
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Form 300 — IVA</h1>
      <div className="flex items-end gap-3 mb-4">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <button
          onClick={generar}
          disabled={!rango.desde || !rango.hasta}
          className="px-4 py-2 rounded bg-geifem-navy text-white text-sm disabled:opacity-50"
        >
          Generar
        </button>
      </div>
      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
      {data && (
        <pre className="bg-white border border-slate-200 rounded p-4 text-xs overflow-auto">
{JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
