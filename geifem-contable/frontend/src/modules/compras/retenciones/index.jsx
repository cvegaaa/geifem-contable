import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [conceptos, setConceptos] = useState([]);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    api
      .get("/api/compras/conceptos-retencion")
      .then((r) => setConceptos(r.data))
      .catch(() => {});
  }, []);

  const generar = async () => {
    setError(null);
    setCargando(true);
    try {
      const params = new URLSearchParams(rango);
      const { data } = await api.get(`/api/compras/retenciones?${params}`);
      setData(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Retenciones practicadas</h1>
      <p className="text-slate-500 text-sm mb-4">
        Resumen de reteFuente, reteICA y reteIVA aplicadas en facturas de proveedor.
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
          <div className="grid gap-3 sm:grid-cols-4 mb-4">
            {Object.entries(data.resumen).map(([k, v]) => (
              <div key={k} className="bg-white border border-slate-200 rounded-lg p-3">
                <p className="text-xs uppercase text-slate-500">{k}</p>
                <p className="text-lg font-semibold text-geifem-navy">{fmtCOP(v)}</p>
              </div>
            ))}
          </div>
          <Table
            columns={[
              { key: "fecha", label: "Fecha" },
              { key: "documento", label: "Documento" },
              { key: "proveedor", label: "Proveedor" },
              { key: "base", label: "Base", render: (r) => fmtCOP(r.base) },
              { key: "retefuente", label: "ReteFuente", render: (r) => fmtCOP(r.retefuente) },
              { key: "reteica", label: "ReteICA", render: (r) => fmtCOP(r.reteica) },
              { key: "reteiva", label: "ReteIVA", render: (r) => fmtCOP(r.reteiva) },
              { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
            ]}
            rows={data.filas}
          />
        </>
      )}

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">
        Conceptos de retención parametrizados
      </h2>
      <Table
        columns={[
          { key: "nombre", label: "Concepto" },
          { key: "tipo", label: "Tipo" },
          { key: "tarifa", label: "Tarifa %" },
        ]}
        rows={conceptos}
        empty="Sin conceptos parametrizados"
      />
    </div>
  );
}
