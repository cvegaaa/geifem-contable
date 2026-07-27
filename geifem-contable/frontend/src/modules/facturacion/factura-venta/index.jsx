import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";

export default function Page() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const cargar = () => api.get("/api/facturacion/facturas").then((r) => setRows(r.data));
  useEffect(() => { cargar(); }, []);
  const enviar = async (id) => {
    setMsg(null);
    try {
      await api.post(`/api/facturacion/facturas/${id}/enviar-dian`);
      cargar();
    } catch (e) { setMsg(e.response?.data?.detail || e.message); }
  };
  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Factura de venta</h1>
      {msg && <div className="text-amber-700 mb-2 text-sm">{msg}</div>}
      <Table
        columns={[
          { key: "fecha", label: "Fecha" },
          { key: "cliente_id", label: "Cliente" },
          { key: "estado_dian", label: "Estado DIAN" },
          { key: "cufe", label: "CUFE" },
          { key: "_a", label: "", render: (r) => (
            <button onClick={() => enviar(r.id)} className="text-xs text-geifem-blue hover:underline">
              Enviar DIAN
            </button>
          )},
        ]}
        rows={rows}
      />
      <p className="text-xs text-slate-500 mt-4">
        Formulario de captura de factura: pendiente ampliación (Fase 1 tardía).
      </p>
    </div>
  );
}
