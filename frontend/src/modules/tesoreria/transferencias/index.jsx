import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import { AccionesDocumento, Avisos, EstadoBadge, fmtCOP, hoy, mensajeError, numeroDoc, useAnulacion } from "../../../shared/documentos/index.jsx";

export default function Page() {
  const { puede } = useAuth();
  const [lista, setLista] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [abierto, setAbierto] = useState(false);
  const [f, setF] = useState({ origen: "", destino: "", fecha: hoy(), valor: "", concepto: "" });
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const [tr, ca, ba] = await Promise.all([
        api.get("/api/tesoreria/transferencias"), api.get("/api/tesoreria/caja"), api.get("/api/tesoreria/bancos"),
      ]);
      setLista(tr.data);
      setCuentas([...ca.data.map((c) => ({ ...c, tipo: "caja" })), ...ba.data.map((c) => ({ ...c, tipo: "banco" }))]);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); }, []);
  const anulacion = useAnulacion(() => { setMensaje("Transferencia anulada"); cargar(); });

  const guardar = async () => {
    setError(null);
    const o = cuentas.find((c) => c.id === f.origen);
    const d = cuentas.find((c) => c.id === f.destino);
    if (!o || !d) return setError("Selecciona la cuenta de origen y la de destino");
    try {
      const { data } = await api.post("/api/tesoreria/transferencias", {
        origen_tipo: o.tipo, origen_id: o.id, destino_tipo: d.tipo, destino_id: d.id,
        fecha: f.fecha, valor: Number(f.valor), concepto: f.concepto || null,
      });
      setMensaje(`Transferencia ${data.numero} registrada por ${fmtCOP(data.valor)}`);
      setAbierto(false);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  const opciones = cuentas.map((c) => (
    <option key={c.id} value={c.id}>{c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre} ({fmtCOP(c.saldo)})</option>
  ));

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Transferencias</h1>
        {puede("tesoreria", "crear") && !abierto && (
          <button onClick={() => { setAbierto(true); setError(null); setMensaje(null); }} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">+ Nueva transferencia</button>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-4">Traslada dinero entre tus cajas y cuentas bancarias (consignaciones, retiros, fondeo de caja menor). No es ingreso ni egreso: solo cambia dónde está el dinero.</p>
      <Avisos error={error} mensaje={mensaje} />
      {abierto && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Sale de"><Select value={f.origen} onChange={(e) => setF({ ...f, origen: e.target.value })}><option value="">Seleccionar…</option>{opciones}</Select></FormField>
            <FormField label="Entra a"><Select value={f.destino} onChange={(e) => setF({ ...f, destino: e.target.value })}><option value="">Seleccionar…</option>{opciones}</Select></FormField>
            <FormField label="Fecha"><Input type="date" value={f.fecha} onChange={(e) => setF({ ...f, fecha: e.target.value })} /></FormField>
            <FormField label="Valor"><Input type="number" value={f.valor} onChange={(e) => setF({ ...f, valor: e.target.value })} /></FormField>
          </div>
          <FormField label="Concepto (opcional)"><Input value={f.concepto} onChange={(e) => setF({ ...f, concepto: e.target.value })} /></FormField>
          <div className="flex gap-2">
            <button onClick={guardar} className="text-sm px-4 py-1.5 rounded-sm bg-geifem-navy text-white">Registrar transferencia</button>
            <button onClick={() => setAbierto(false)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">Cancelar</button>
          </div>
        </div>
      )}
      <Table
        titulo="Transferencias"
        columns={[
          { key: "numero", label: "Número", render: (r) => <b>{numeroDoc(r)}</b> },
          { key: "fecha", label: "Fecha" },
          { key: "origen_nombre", label: "Sale de" },
          { key: "destino_nombre", label: "Entra a" },
          { key: "concepto", label: "Concepto" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          { key: "_acc", label: "", render: (r) => <AccionesDocumento tipoDoc="transferencia" doc={r} modulo="tesoreria" onAnular={(d) => anulacion.pedir(d, `/api/tesoreria/transferencias/${d.id}/anular`)} /> },
        ]}
        rows={lista}
        empty="Sin transferencias"
      />
      {anulacion.modal}
    </div>
  );
}
