import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, EstadoBadge, fmtCOP, mensajeError, numeroDoc } from "../../../shared/documentos/index.jsx";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

export default function Page() {
  const { puede } = useAuth();
  const hoyD = new Date();
  // Por defecto el mes anterior: es el que corresponde transmitir.
  const anterior = new Date(hoyD.getFullYear(), hoyD.getMonth() - 1, 1);
  const [mes, setMes] = useState({ anio: anterior.getFullYear(), mes: anterior.getMonth() + 1 });
  const [docs, setDocs] = useState([]);
  const [ver, setVer] = useState(null);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [trabajando, setTrabajando] = useState(false);

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/nomina/electronica", { params: mes });
      setDocs(data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, [mes.anio, mes.mes]);

  const generar = async () => {
    setError(null); setMensaje(null); setTrabajando(true);
    try {
      const { data } = await api.post("/api/nomina/electronica/generar", mes);
      setMensaje(`${data.generados.length} documento(s) generado(s)` + (data.omitidos.length ? `; omitidos: ${data.omitidos.map((o) => `${o.empleado} (${o.motivo})`).join(", ")}` : ""));
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setTrabajando(false);
    }
  };

  const transmitir = async (d) => {
    setError(null); setMensaje(null);
    try {
      await api.post(`/api/nomina/electronica/${d.id}/transmitir`);
      setMensaje(`${d.numero} transmitido`);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const verDocumento = async (d) => {
    try {
      const { data } = await api.get(`/api/nomina/electronica/${d.id}/documento`);
      setVer({ doc: d, json: data });
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const descargar = (d, json) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(json, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${d.numero}-${d.documento_empleado}-${mes.anio}-${String(mes.mes).padStart(2, "0")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Nómina electrónica</h1>
      <p className="text-sm text-slate-500 mb-3">
        Se genera <b>un documento por empleado y por mes</b>, consolidando todos sus pagos del mes (mensuales o quincenales), y se transmite a la DIAN
        a través de Alegra dentro del plazo del mes siguiente. Las correcciones se hacen con notas de ajuste.
      </p>
      <p className="mb-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
        La transmisión con Alegra aún no está habilitada: falta confirmar su API de emisión de nómina electrónica y las credenciales de la empresa.
        Mientras tanto el paquete mensual queda generado y se puede descargar en JSON. Para generarlo, todas las liquidaciones del mes deben estar pagadas
        (la DIAN exige la fecha de pago).
      </p>
      <Avisos error={error} mensaje={mensaje} />

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <FormField label="Año"><Input type="number" value={mes.anio} onChange={(e) => setMes({ ...mes, anio: Number(e.target.value) })} /></FormField>
        <FormField label="Mes"><Select value={mes.mes} onChange={(e) => setMes({ ...mes, mes: Number(e.target.value) })}>{MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</Select></FormField>
        {puede("nomina", "crear") && (
          <button onClick={generar} disabled={trabajando} className="mb-3 bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60">
            {trabajando ? "Generando…" : docs.length ? "Regenerar borradores" : "Generar nómina electrónica del mes"}
          </button>
        )}
      </div>

      <Table
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
          { key: "empleado_nombre", label: "Empleado" }, { key: "documento_empleado", label: "Documento" },
          { key: "periodos", label: "Liquidaciones", render: (r) => r.periodos?.join(", ") },
          { key: "devengados", label: "Devengado", render: (r) => fmtCOP(r.devengados) },
          { key: "deducciones", label: "Deducciones", render: (r) => fmtCOP(r.deducciones) },
          { key: "neto", label: "Neto", render: (r) => <b>{fmtCOP(r.neto)}</b> },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          { key: "cune", label: "CUNE", render: (r) => (r.cune ? `${r.cune.slice(0, 10)}…` : "—") },
          { key: "_a", label: "", render: (r) => (
            <div className="flex gap-3 whitespace-nowrap">
              <button onClick={() => verDocumento(r)} className="text-xs text-geifem-blue hover:underline">Ver paquete</button>
              {r.estado === "borrador" && puede("nomina", "editar") && <button onClick={() => transmitir(r)} className="text-xs text-emerald-700 hover:underline">Transmitir</button>}
            </div>
          ) },
        ]}
        rows={docs} empty="Aún no hay documentos de este mes"
      />

      <Modal open={Boolean(ver)} onClose={() => setVer(null)} title={ver ? `${ver.doc.empleado_nombre} · ${MESES[mes.mes - 1]} ${mes.anio}` : ""}
        footer={<><button onClick={() => setVer(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cerrar</button><button onClick={() => descargar(ver.doc, ver.json)} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Descargar JSON</button></>}>
        {ver && (
          <>
            <p className="text-xs text-slate-500 mb-2">Pagos del mes: {ver.json.FechasPagos.join(", ")} · Devengado {fmtCOP(ver.json.DevengadosTotal)} · Deducciones {fmtCOP(ver.json.DeduccionesTotal)}</p>
            <pre className="text-[11px] bg-slate-50 border border-slate-200 rounded-sm p-2 overflow-auto max-h-96">{JSON.stringify(ver.json, null, 2)}</pre>
          </>
        )}
      </Modal>
    </div>
  );
}
