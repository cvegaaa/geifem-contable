import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input } from "../../../shared/layout/FormField/index.jsx";

export default function Page() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ producto_id: "", tipo: "entrada", cantidad: 0, costo_unitario: 0, fecha: new Date().toISOString().slice(0,10) });
  const [msg, setMsg] = useState(null);
  const cargar = (pid) => api.get(`/api/inventario/kardex/movimientos${pid ? `?producto_id=${pid}` : ""}`).then((r) => setRows(r.data));
  useEffect(() => { cargar(); }, []);
  const registrar = async (e) => {
    e.preventDefault();
    setMsg(null);
    try {
      await api.post("/api/inventario/kardex/movimientos", { ...form, cantidad: Number(form.cantidad), costo_unitario: Number(form.costo_unitario) });
      cargar(form.producto_id);
    } catch (err) { setMsg(err.response?.data?.detail || err.message); }
  };
  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-4">Kardex — Promedio Ponderado</h1>
      <form onSubmit={registrar} className="bg-white p-4 rounded-lg border border-slate-200 grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <FormField label="Producto (id)"><Input value={form.producto_id} onChange={(e) => setForm({ ...form, producto_id: e.target.value })} /></FormField>
        <FormField label="Tipo">
          <select className="border border-slate-300 rounded px-3 py-2 w-full" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
            <option value="entrada">Entrada</option>
            <option value="salida">Salida</option>
            <option value="ajuste">Ajuste</option>
          </select>
        </FormField>
        <FormField label="Cantidad"><Input type="number" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} /></FormField>
        <FormField label="Costo unitario"><Input type="number" value={form.costo_unitario} onChange={(e) => setForm({ ...form, costo_unitario: e.target.value })} /></FormField>
        <FormField label="Fecha"><Input type="date" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} /></FormField>
        <div className="col-span-full"><button className="bg-geifem-navy text-white px-4 py-2 rounded text-sm">Registrar</button></div>
      </form>
      {msg && <div className="text-red-600 mb-2 text-sm">{msg}</div>}
      <Table
        columns={[
          { key: "fecha", label: "Fecha" },
          { key: "producto_id", label: "Producto" },
          { key: "tipo", label: "Tipo" },
          { key: "cantidad", label: "Cantidad" },
          { key: "costo_unitario", label: "Costo unit." },
          { key: "referencia_documento", label: "Ref" },
        ]}
        rows={rows}
      />
    </div>
  );
}
