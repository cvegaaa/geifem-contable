import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import SelectorRangoFechas from "../../../shared/selector-rango-fechas/index.jsx";

export default function Page() {
  const [rango, setRango] = useState({ desde: "", hasta: "" });
  const [tipo, setTipo] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  const cargar = async () => {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (rango.desde) params.set("desde", rango.desde);
      if (rango.hasta) params.set("hasta", rango.hasta);
      if (tipo) params.set("tipo", tipo);
      const { data } = await api.get(`/api/contabilidad/comprobantes?${params}`);
      setRows(data);
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  };

  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, []);

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Consulta de comprobantes</h1>
      <div className="flex gap-3 mb-3 items-end flex-wrap">
        <SelectorRangoFechas value={rango} onChange={setRango} />
        <div>
          <label className="block text-xs uppercase text-slate-500 mb-1">Tipo</label>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1 text-sm"
          >
            <option value="">Todos</option>
            <option value="ajuste">Ajuste</option>
            <option value="nota">Nota</option>
            <option value="apertura">Apertura</option>
            <option value="cierre">Cierre</option>
          </select>
        </div>
        <button onClick={cargar} className="px-3 py-1.5 bg-geifem-navy text-white text-sm rounded">
          Consultar
        </button>
      </div>
      {error && <div className="text-red-600 mb-2 text-sm">{error}</div>}
      <Table
        columns={[
          { key: "consecutivo", label: "#" },
          { key: "tipo", label: "Tipo" },
          { key: "fecha", label: "Fecha" },
          { key: "estado", label: "Estado" },
          { key: "descripcion", label: "Descripción" },
        ]}
        rows={rows}
      />
    </div>
  );
}
