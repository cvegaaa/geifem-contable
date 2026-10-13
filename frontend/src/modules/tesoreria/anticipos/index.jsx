import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import {
  AccionesDocumento,
  Avisos,
  EstadoBadge,
  fmtCOP,
  hoy,
  mensajeError,
  numeroDoc,
  useAnulacion,
} from "../../../shared/documentos/index.jsx";

const NUEVO = { tipo: "cliente", tercero_id: "", fecha: hoy(), valor: "", cuenta: "", observaciones: "" };

export default function Page() {
  const { puede } = useAuth();
  const [anticipos, setAnticipos] = useState([]);
  const [aplicaciones, setAplicaciones] = useState([]);
  const [terceros, setTerceros] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [cartera, setCartera] = useState({ cxc: [], cxp: [] });
  const [form, setForm] = useState(null);
  const [aplicar, setAplicar] = useState(null);
  const [error, setError] = useState(null);
  const [errorModal, setErrorModal] = useState(null);
  const [mensaje, setMensaje] = useState(null);

  const cargar = async () => {
    try {
      const [an, ap, te, ca, ba, ct] = await Promise.all([
        api.get("/api/tesoreria/anticipos"),
        api.get("/api/tesoreria/aplicaciones-anticipo"),
        api.get("/api/configuracion/terceros"),
        api.get("/api/tesoreria/caja"),
        api.get("/api/tesoreria/bancos"),
        api.get("/api/tesoreria/cxc-cxp"),
      ]);
      setAnticipos(an.data);
      setAplicaciones(ap.data);
      setTerceros(te.data);
      setCuentas([...ca.data.map((c) => ({ ...c, tipo: "caja" })), ...ba.data.map((c) => ({ ...c, tipo: "banco" }))]);
      setCartera(ct.data);
    } catch (e) {
      setError(mensajeError(e));
    }
  };
  useEffect(() => { cargar(); }, []);

  const anularAnticipo = useAnulacion(() => { setMensaje("Anticipo anulado"); cargar(); });
  const anularAplicacion = useAnulacion(() => { setMensaje("Aplicación anulada: el saldo volvió al anticipo y a la factura"); cargar(); });

  const guardar = async () => {
    setErrorModal(null);
    const cuenta = cuentas.find((c) => c.id === form.cuenta);
    if (!form.tercero_id) return setErrorModal("Selecciona el tercero");
    if (!cuenta) return setErrorModal("Selecciona la caja o el banco");
    if (!(Number(form.valor) > 0)) return setErrorModal("Indica el valor");
    try {
      const { data } = await api.post("/api/tesoreria/anticipos", {
        tipo: form.tipo, tercero_id: form.tercero_id, fecha: form.fecha, valor: Number(form.valor),
        cuenta_tipo: cuenta.tipo, cuenta_id: cuenta.id, observaciones: form.observaciones || null,
      });
      setMensaje(`Anticipo ${data.numero} registrado por ${fmtCOP(data.valor)}`);
      setForm(null);
      cargar();
    } catch (e) {
      setErrorModal(mensajeError(e));
    }
  };

  const abrirAplicar = (a) => {
    setErrorModal(null);
    const abiertas = (a.tipo === "cliente" ? cartera.cxc : cartera.cxp).filter((d) => d.tercero_id === a.tercero_id);
    setAplicar({ anticipo: a, abiertas, documento_id: abiertas[0]?.id || "", fecha: hoy(), valor: Math.min(a.saldo, abiertas[0]?.saldo || 0) });
  };

  const confirmarAplicar = async () => {
    setErrorModal(null);
    try {
      const { data } = await api.post(`/api/tesoreria/anticipos/${aplicar.anticipo.id}/aplicar`, {
        documento_id: aplicar.documento_id, fecha: aplicar.fecha, valor: Number(aplicar.valor),
      });
      setMensaje(`${data.numero}: ${fmtCOP(data.valor)} aplicados a ${data.documento_numero}`);
      setAplicar(null);
      cargar();
    } catch (e) {
      setErrorModal(mensajeError(e));
    }
  };

  const candidatos = terceros.filter((t) =>
    form?.tipo === "cliente" ? ["cliente", "ambos"].includes(t.tipo) || !t.tipo : ["proveedor", "ambos"].includes(t.tipo) || !t.tipo
  );

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-bold text-geifem-navy">Anticipos</h1>
        {puede("tesoreria", "crear") && (
          <button onClick={() => { setForm({ ...NUEVO, fecha: hoy() }); setErrorModal(null); }} className="text-sm px-4 py-2 rounded-sm bg-geifem-navy text-white hover:bg-geifem-blue">
            + Nuevo anticipo
          </button>
        )}
      </div>
      <p className="text-sm text-slate-500 mb-4">
        Dinero recibido de un cliente o entregado a un proveedor antes de facturar. Queda en una cuenta de anticipos y luego se aplica a sus facturas sin mover efectivo.
      </p>
      <Avisos error={error} mensaje={mensaje} />

      <Table
        titulo="Anticipos"
        columns={[
          { key: "numero", label: "Número", render: (r) => <b>{numeroDoc(r)}</b> },
          { key: "tipo", label: "Tipo", render: (r) => (r.tipo === "cliente" ? "De cliente" : "A proveedor") },
          { key: "fecha", label: "Fecha" },
          { key: "tercero_nombre", label: "Tercero" },
          { key: "cuenta_nombre", label: "Caja / banco" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "saldo", label: "Por aplicar", render: (r) => fmtCOP(r.saldo) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acc", label: "",
            render: (r) => (
              <div className="flex gap-3 whitespace-nowrap">
                {r.estado !== "anulado" && r.saldo > 0.009 && puede("tesoreria", "crear") && (
                  <button onClick={() => abrirAplicar(r)} className="text-xs text-geifem-blue hover:underline">Aplicar a factura</button>
                )}
                <AccionesDocumento tipoDoc="anticipo" doc={r} modulo="tesoreria"
                  onAnular={(d) => anularAnticipo.pedir(d, `/api/tesoreria/anticipos/${d.id}/anular`)} />
              </div>
            ),
          },
        ]}
        rows={anticipos}
        empty="Sin anticipos registrados"
      />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Aplicaciones a facturas</h2>
      <Table
        titulo="Aplicaciones de anticipos"
        columns={[
          { key: "numero", label: "Número", render: (r) => <b>{numeroDoc(r)}</b> },
          { key: "fecha", label: "Fecha" },
          { key: "anticipo_numero", label: "Anticipo" },
          { key: "tercero_nombre", label: "Tercero" },
          { key: "documento_numero", label: "Factura" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acc", label: "",
            render: (r) => <AccionesDocumento doc={r} modulo="tesoreria"
              onAnular={(d) => anularAplicacion.pedir(d, `/api/tesoreria/aplicaciones-anticipo/${d.id}/anular`)} />,
          },
        ]}
        rows={aplicaciones}
        empty="Sin aplicaciones"
      />

      <Modal
        open={Boolean(form)} onClose={() => setForm(null)} title="Nuevo anticipo"
        footer={<>
          <button onClick={() => setForm(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={guardar} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white">Registrar</button>
        </>}
      >
        {form && (
          <>
            <FormField label="Tipo">
              <Select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value, tercero_id: "" })}>
                <option value="cliente">Anticipo recibido de un cliente</option>
                <option value="proveedor">Anticipo entregado a un proveedor</option>
              </Select>
            </FormField>
            <FormField label="Tercero">
              <Select value={form.tercero_id} onChange={(e) => setForm({ ...form, tercero_id: e.target.value })}>
                <option value="">Seleccionar…</option>
                {candidatos.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
              </Select>
            </FormField>
            <FormField label={form.tipo === "cliente" ? "Entra a" : "Sale de"}>
              <Select value={form.cuenta} onChange={(e) => setForm({ ...form, cuenta: e.target.value })}>
                <option value="">Seleccionar…</option>
                {cuentas.map((c) => <option key={c.id} value={c.id}>{c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre}</option>)}
              </Select>
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="Fecha"><Input type="date" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} /></FormField>
              <FormField label="Valor"><Input type="number" value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })} /></FormField>
            </div>
            <FormField label="Observaciones"><Input value={form.observaciones} onChange={(e) => setForm({ ...form, observaciones: e.target.value })} /></FormField>
            {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
          </>
        )}
      </Modal>

      <Modal
        open={Boolean(aplicar)} onClose={() => setAplicar(null)} title={aplicar ? `Aplicar ${aplicar.anticipo.numero}` : ""}
        footer={<>
          <button onClick={() => setAplicar(null)} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Cancelar</button>
          <button onClick={confirmarAplicar} disabled={!aplicar?.documento_id} className="px-4 py-1.5 text-sm rounded-sm bg-geifem-navy text-white disabled:opacity-50">Aplicar</button>
        </>}
      >
        {aplicar && (
          <>
            <p className="text-sm text-slate-600 mb-3">{aplicar.anticipo.tercero_nombre} · disponible {fmtCOP(aplicar.anticipo.saldo)}</p>
            {aplicar.abiertas.length === 0 ? (
              <p className="text-sm text-amber-700">Este tercero no tiene facturas con saldo pendiente.</p>
            ) : (
              <>
                <FormField label="Factura">
                  <Select value={aplicar.documento_id} onChange={(e) => {
                    const d = aplicar.abiertas.find((x) => x.id === e.target.value);
                    setAplicar({ ...aplicar, documento_id: e.target.value, valor: Math.min(aplicar.anticipo.saldo, d?.saldo || 0) });
                  }}>
                    {aplicar.abiertas.map((d) => <option key={d.id} value={d.id}>{d.documento} — saldo {fmtCOP(d.saldo)}</option>)}
                  </Select>
                </FormField>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Fecha"><Input type="date" value={aplicar.fecha} onChange={(e) => setAplicar({ ...aplicar, fecha: e.target.value })} /></FormField>
                  <FormField label="Valor a aplicar"><Input type="number" value={aplicar.valor} onChange={(e) => setAplicar({ ...aplicar, valor: e.target.value })} /></FormField>
                </div>
              </>
            )}
            {errorModal && <p className="text-sm text-red-600">{errorModal}</p>}
          </>
        )}
      </Modal>
      {anularAnticipo.modal}
      {anularAplicacion.modal}
    </div>
  );
}
