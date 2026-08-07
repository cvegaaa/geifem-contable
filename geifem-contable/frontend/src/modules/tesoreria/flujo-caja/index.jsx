import { useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  const generar = async () => {
    setError(null);
    setCargando(true);
    try {
      const params = new URLSearchParams(rango);
      const { data } = await api.get(`/api/tesoreria/flujo-caja?${params}`);
      setData(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Flujo de caja</h1>
      <p className="text-slate-500 text-sm mb-4">
        Ingresos y egresos de tesorería por día, con saldo acumulado del período.
      </p>

      <div className="flex items-end gap-3 mb-4 flex-wrap">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <button
          onClick={generar}
          disabled={!rango.desde || !rango.hasta || cargando}
          className="px-4 py-2 rounded bg-geifem-navy text-white text-sm disabled:opacity-50"
        >
          {cargando ? "Generando…" : "Generar"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3 mb-4">
            {Object.entries(data.resumen).map(([k, v]) => (
              <div key={k} className="bg-white border border-slate-200 rounded-lg p-3">
                <p className="text-xs uppercase text-slate-500">{k}</p>
                <p className="text-lg font-semibold text-geifem-navy">{fmtCOP(v)}</p>
              </div>
            ))}
          </div>
          <Table
            columns={data.columnas.map((c) =>
              c.key === "fecha" ? c : { ...c, render: (r) => fmtCOP(r[c.key]) }
            )}
            rows={data.filas}
          />
        </>
      )}
    </div>
  );
}
