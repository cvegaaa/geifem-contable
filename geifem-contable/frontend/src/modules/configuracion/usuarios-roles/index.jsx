import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";

export default function Page() {
  const [usuarios, setUsuarios] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/api/configuracion/usuarios-roles")
      .then((r) => setUsuarios(r.data))
      .catch((e) => setError(e.response?.data?.detail || e.message));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Usuarios y roles</h1>
      {error && <div className="text-red-600 mb-3">{error}</div>}
      <Table
        columns={[
          { key: "nombre", label: "Nombre" },
          { key: "email", label: "Email" },
          { key: "rol", label: "Rol" },
          { key: "activo", label: "Activo", render: (r) => (r.activo ? "Sí" : "No") },
        ]}
        rows={usuarios}
      />
      <p className="text-xs text-slate-500 mt-4">
        Creación y edición fina de permisos: pendiente ampliación posterior.
      </p>
    </div>
  );
}
