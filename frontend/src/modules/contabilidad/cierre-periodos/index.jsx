import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, mensajeError } from "../../../shared/documentos/index.jsx";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const finDeMes = (anio, mes) => `${anio}-${String(mes).padStart(2, "0")}-${String(new Date(anio, mes, 0).getDate()).padStart(2, "0")}`;

const formatear = (f) => {
  if (!f) return "Sin cierre";
  const [a, m, d] = f.split("-");
  return `${Number(d)} de ${MESES[Number(m) - 1].toLowerCase()} de ${a}`;
};

export default function Page() {
  const { usuario, puede } = useAuth();
  const [estado, setEstado] = useState({ fecha_cierre: null, historial: [] });
  const hoy = new Date();
  // Último mes terminado por defecto
  const previo = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);
  const [sel, setSel] = useState({ anio: previo.getFullYear(), mes: previo.getMonth() + 1 });
  const [reabrir, setReabrir] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const { data } = await api.get("/api/contabilidad/cierre");
      setEstado(data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };
  useEffect(() => { cargar(); }, []);

  const cerrar = async () => {
    setError(null); setMensaje(null);
    const fecha = finDeMes(Number(sel.anio), Number(sel.mes));
    try {
      const { data } = await api.put("/api/contabilidad/cierre", { fecha_cierre: fecha });
      setEstado(data);
      setMensaje(`Contabilidad cerrada hasta el ${formatear(fecha)}`);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const reabrirHasta = async (fecha) => {
    setError(null); setMensaje(null);
    try {
      const { data } = await api.put("/api/contabilidad/cierre", { fecha_cierre: fecha, motivo });
      setEstado(data);
      setReabrir(false);
      setMotivo("");
      setMensaje(fecha ? `Periodo reabierto: ahora el cierre es hasta el ${formatear(fecha)}` : "Periodos reabiertos: no hay fecha de cierre");
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const esAdmin = usuario?.rol === "admin";
  const anterior = estado.fecha_cierre ? (() => {
    const [a, m] = estado.fecha_cierre.split("-").map(Number);
    return m === 1 ? null : finDeMes(a, m - 1);
  })() : null;

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Cierre de periodos</h1>
      <p className="text-sm text-slate-500 mb-4">
        Al cerrar un mes nadie puede crear, modificar ni anular documentos con fecha dentro de él, en ningún módulo. Los errores se corrigen
        con un comprobante de ajuste en el periodo abierto. Cierra el mes cuando ya presentaste sus declaraciones.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5">
        <div className="text-sm text-slate-500">Contabilidad cerrada hasta</div>
        <div className="text-2xl font-bold text-geifem-navy">{formatear(estado.fecha_cierre)}</div>
        {estado.fecha_cierre && esAdmin && (
          <div className="mt-3 flex gap-3">
            {anterior && <button onClick={() => setReabrir(anterior)} className="text-sm border border-slate-300 rounded-sm px-3 py-1.5">Reabrir el último mes</button>}
            <button onClick={() => setReabrir("todo")} className="text-sm border border-amber-400 text-amber-700 rounded-sm px-3 py-1.5">Reabrir todo</button>
          </div>
        )}
      </div>

      {puede("contabilidad", "editar") && (
        <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5">
          <h2 className="font-semibold text-geifem-navy mb-2">Cerrar un mes</h2>
          <div className="flex flex-wrap gap-3 items-end">
            <FormField label="Año"><Input type="number" value={sel.anio} onChange={(e) => setSel({ ...sel, anio: e.target.value })} /></FormField>
            <FormField label="Mes">
              <Select value={sel.mes} onChange={(e) => setSel({ ...sel, mes: e.target.value })}>
                {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </Select>
            </FormField>
            <button onClick={cerrar} className="mb-3 bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm">Cerrar hasta fin de {MESES[sel.mes - 1].toLowerCase()}</button>
          </div>
          <p className="text-xs text-slate-500">Cerrar un mes cierra también todos los anteriores. No se puede cerrar con comprobantes en borrador dentro del periodo.</p>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Historial</h2>
      <Table
        columns={[
          { key: "fecha_hora", label: "Fecha y hora", render: (r) => new Date(r.fecha_hora).toLocaleString("es-CO") },
          { key: "accion", label: "Acción", render: (r) => <span className="capitalize">{r.accion}</span> },
          { key: "numero", label: "Cierre hasta", render: (r) => (r.numero === "abierto" ? "Sin cierre" : r.numero) },
          { key: "motivo", label: "Motivo", render: (r) => r.detalle?.motivo || "" },
        ]}
        rows={estado.historial} empty="Aún no se ha cerrado ningún periodo"
      />

      <Modal
        open={Boolean(reabrir)} onClose={() => setReabrir(false)} title="Reabrir periodo"
        footer={<>
          <button onClick={() => setReabrir(false)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
          <button onClick={() => reabrirHasta(reabrir === "todo" ? null : reabrir)} className="px-3 py-1.5 rounded-sm bg-amber-600 text-white text-sm">Reabrir</button>
        </>}
      >
        <p className="text-sm text-slate-600 mb-3">
          Reabrir permite modificar documentos de meses ya cerrados, lo que puede alterar declaraciones presentadas. Queda registrado con tu motivo.
        </p>
        <FormField label="Motivo (obligatorio)"><Input value={motivo} onChange={(e) => setMotivo(e.target.value)} /></FormField>
      </Modal>
    </div>
  );
}
