import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";

export default function Page() {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api.get("/api/contabilidad/auditoria").then((r) => setRows(r.data)).catch(() => setRows([]));
  }, []);
  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Auditoría de comprobantes</h1>
      <p className="text-xs text-slate-500 mb-3">Registro de solo lectura.</p>
      <Table
        columns={[
          { key: "fecha_hora", label: "Fecha/hora", render: (r) => new Date(r.fecha_hora).toLocaleString() },
          { key: "accion", label: "Acción" },
          { key: "comprobante_id", label: "Comprobante" },
          { key: "usuario_id", label: "Usuario" },
        ]}
        rows={rows}
      />
    </div>
  );
}
