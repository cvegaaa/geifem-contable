import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

const TARJETAS = [
  ["base", "Base sujeta a retención"],
  ["retefuente", "ReteFuente (renta)"],
  ["reteiva", "ReteIVA"],
  ["reteica", "ReteICA"],
  ["total", "Total a declarar"],
];

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
      const { data } = await api.get(`/api/reportes/fiscales/formulario-350?${params}`);
      setData(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div>
      <p className="text-sm text-geifem-blue mb-1">
        <Link to="/reportes">Reportes</Link> › <Link to="/reportes/fiscales">Fiscales</Link>
      </p>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">
        Formulario 350 — Retenciones en la fuente
      </h1>
      <p className="text-slate-500 text-sm mb-4">
        Consolidado de las retenciones practicadas a proveedores en el periodo. Cifras
        referenciales para el diligenciamiento del formulario oficial ante la DIAN.
      </p>

      <div className="flex items-end gap-3 mb-4 flex-wrap">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <button
          onClick={generar}
          disabled={!rango.desde || !rango.hasta || cargando}
          className="px-4 py-2 rounded-sm bg-geifem-navy text-white text-sm disabled:opacity-50"
        >
          {cargando ? "Generando…" : "Generar"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-5 mb-4">
            {TARJETAS.map(([k, label]) => (
              <div key={k} className="bg-white border border-slate-200 rounded-lg p-3">
                <p className="text-xs uppercase text-slate-500">{label}</p>
                <p className="text-lg font-semibold text-geifem-navy">
                  {fmtCOP(data.resumen?.[k])}
                </p>
              </div>
            ))}
          </div>

          <Table
            columns={[
              { key: "concepto", label: "Concepto" },
              { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
            ]}
            rows={data.filas || []}
            empty="Sin retenciones en el periodo"
          />
        </>
      )}
    </div>
  );
}
