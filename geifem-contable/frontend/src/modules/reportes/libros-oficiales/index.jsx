import { useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";
import FormField, { Select } from "../../../shared/layout/FormField/index.jsx";

const LIBROS = [
  { slug: "diario", titulo: "Libro diario" },
  { slug: "mayor-y-balances", titulo: "Libro mayor y balances" },
  { slug: "inventarios-y-balances", titulo: "Libro de inventarios y balances" },
];

export default function Page() {
  const [libro, setLibro] = useState("diario");
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  const generar = async () => {
    setError(null);
    setData(null);
    setCargando(true);
    try {
      const params = new URLSearchParams({ ...rango, libro });
      const { data } = await api.get(`/api/reportes/libros-oficiales?${params}`);
      setData(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Libros oficiales</h1>
      <p className="text-slate-500 text-sm mb-4">
        Libros contables oficiales con numeración consecutiva de folios por período.
      </p>

      <div className="flex items-end gap-3 mb-4 flex-wrap">
        <div className="w-64">
          <FormField label="Libro">
            <Select value={libro} onChange={(e) => setLibro(e.target.value)}>
              {LIBROS.map((l) => (
                <option key={l.slug} value={l.slug}>
                  {l.titulo}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <button
          onClick={generar}
          disabled={!rango.desde || !rango.hasta || cargando}
          className="px-4 py-2 rounded bg-geifem-navy text-white text-sm disabled:opacity-50 mb-3"
        >
          {cargando ? "Generando…" : "Generar"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}

      {data && (
        <>
          <p className="text-sm text-slate-600 mb-3">
            {data.libro} · {data.periodo.desde} a {data.periodo.hasta} · {data.folios} folios
          </p>
          <Table columns={data.columnas} rows={data.filas} />
        </>
      )}
    </div>
  );
}
