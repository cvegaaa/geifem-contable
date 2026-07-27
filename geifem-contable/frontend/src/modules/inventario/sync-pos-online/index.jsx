import { useState } from "react";
import api from "../../../core/api.js";

export default function Page() {
  const [msg, setMsg] = useState(null);
  const disparar = async () => {
    const { data } = await api.post("/api/inventario/sync/pos-online");
    setMsg(data.detail);
  };
  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-2">Sync POS / Online</h1>
      <p className="text-slate-500 mb-4">Sincroniza inventario entre canal físico y en línea.</p>
      <button onClick={disparar} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded">
        Ejecutar sincronización
      </button>
      {msg && <p className="mt-3 text-sm text-slate-700">{msg}</p>}
    </div>
  );
}
