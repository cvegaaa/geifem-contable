import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../../core/api.js";
import Table from "../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../shared/selector-rango-fechas/index.jsx";
import { buscarReporte } from "./_catalogo.js";

export default function VistaReporte() {
  const { categoria, slug } = useParams();
  const { categoria: cat, reporte } = buscarReporte(categoria, slug);
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  if (!reporte) return <p className="text-slate-500">Reporte no encontrado.</p>;

  const generar = async () => {
    setError(null);
    setData(null);
    setCargando(true);
    try {
      const params = new URLSearchParams(rango);
      const { data } = await api.get(`/api/reportes/${categoria}/${slug}?${params}`);
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
        <Link to="/reportes">Reportes</Link> ›{" "}
        <Link to={`/reportes/${cat.slug}`}>{cat.titulo}</Link>
      </p>
      <h1 className="text-2xl font-bold text-geifem-navy">{reporte.titulo}</h1>
      <p className="text-slate-500 mb-4">{reporte.descripcion}</p>

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

      {data?.resumen && Object.keys(data.resumen).length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-4 mb-4">
          {Object.entries(data.resumen).map(([k, v]) => (
            <div key={k} className="bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs uppercase text-slate-500">{k.replace(/_/g, " ")}</p>
              <p className="text-lg font-semibold text-geifem-navy">
                {typeof v === "number" ? v.toLocaleString("es-CO") : String(v)}
              </p>
            </div>
          ))}
        </div>
      )}

      {data?.columnas && <Table columns={data.columnas} rows={data.filas || []} />}
    </div>
  );
}
