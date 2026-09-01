import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export default function Page() {
  const [cartera, setCartera] = useState({ cxc: [], cxp: [], resumen: {} });
  const [cuentas, setCuentas] = useState([]);
  const [pagos, setPagos] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [doc, setDoc] = useState(null);
  const [pago, setPago] = useState({
    cuenta_tipo: "caja",
    cuenta_id: "",
    fecha: new Date().toISOString().slice(0, 10),
    valor: 0,
    observaciones: "",
  });

  const cargar = async () => {
    try {
      const [c, caja, banco, pg] = await Promise.all([
        api.get("/api/tesoreria/cxc-cxp"),
        api.get("/api/tesoreria/caja"),
        api.get("/api/tesoreria/bancos"),
        api.get("/api/tesoreria/pagos"),
      ]);
      setCartera(c.data);
      setCuentas([
        ...caja.data.map((x) => ({ ...x, tipo: "caja" })),
        ...banco.data.map((x) => ({ ...x, tipo: "banco" })),
      ]);
      setPagos(pg.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const abrirCruce = (d) => {
    setDoc(d);
    setPago({ ...pago, valor: d.saldo, cuenta_id: "" });
  };

  const registrarPago = async () => {
    setError(null);
    try {
      const cuenta = cuentas.find((c) => c.id === pago.cuenta_id);
      const { data } = await api.post("/api/tesoreria/pagos", {
        documento_tipo: doc.tipo,
        documento_id: doc.id,
        cuenta_tipo: cuenta.tipo,
        cuenta_id: cuenta.id,
        fecha: pago.fecha,
        valor: Number(pago.valor),
        observaciones: pago.observaciones || null,
      });
      setMensaje(
        `${data.referencia} aplicado a ${data.documento_numero} — saldo restante ${fmtCOP(
          data.saldo_resultante
        )}`
      );
      setDoc(null);
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const columnas = [
    { key: "fecha", label: "Fecha" },
    { key: "documento", label: "Documento" },
    { key: "tercero", label: "Tercero" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "saldo", label: "Saldo", render: (r) => fmtCOP(r.saldo) },
    {
      key: "_acc",
      label: "Acciones",
      render: (r) => (
        <button onClick={() => abrirCruce(r)} className="text-xs text-geifem-blue hover:underline">
          Cruzar pago
        </button>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Cuentas por cobrar / pagar</h1>
      <p className="text-slate-500 text-sm mb-4">
        Cruza recaudos y pagos contra facturas; cada cruce genera movimiento de tesorería y asiento
        contable.
      </p>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {mensaje && <div className="mb-3 text-sm text-green-700">{mensaje}</div>}

      <div className="grid gap-3 sm:grid-cols-2 mb-5">
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <p className="text-xs uppercase text-slate-500">Total por cobrar</p>
          <p className="text-lg font-semibold text-geifem-navy">
            {fmtCOP(cartera.resumen?.total_cxc)}
          </p>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-3">
          <p className="text-xs uppercase text-slate-500">Total por pagar</p>
          <p className="text-lg font-semibold text-geifem-navy">
            {fmtCOP(cartera.resumen?.total_cxp)}
          </p>
        </div>
      </div>

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Cuentas por cobrar</h2>
      <Table columns={columnas} rows={cartera.cxc} empty="Sin cartera pendiente" />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Cuentas por pagar</h2>
      <Table columns={columnas} rows={cartera.cxp} empty="Sin obligaciones pendientes" />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Pagos y recaudos aplicados</h2>
      <Table
        columns={[
          { key: "fecha", label: "Fecha" },
          { key: "referencia", label: "Documento" },
          { key: "documento_numero", label: "Aplica a" },
          { key: "tercero_nombre", label: "Tercero" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "saldo_resultante", label: "Saldo", render: (r) => fmtCOP(r.saldo_resultante) },
        ]}
        rows={pagos}
        empty="Sin cruces registrados"
      />

      <Modal
        open={!!doc}
        onClose={() => setDoc(null)}
        title={doc ? `Cruce ${doc.tipo.toUpperCase()} — ${doc.documento}` : ""}
        footer={
          <>
            <button onClick={() => setDoc(null)} className="px-3 py-1.5 rounded border border-slate-300 text-sm">
              Cancelar
            </button>
            <button onClick={registrarPago} className="px-3 py-1.5 rounded bg-geifem-navy text-white text-sm">
              Aplicar
            </button>
          </>
        }
      >
        {doc && (
          <>
            <p className="text-sm text-slate-600 mb-3">
              {doc.tercero} · saldo pendiente {fmtCOP(doc.saldo)}
            </p>
            <FormField label="Cuenta de tesorería">
              <Select value={pago.cuenta_id} onChange={(e) => setPago({ ...pago, cuenta_id: e.target.value })}>
                <option value="">Seleccione…</option>
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.tipo === "caja" ? "Caja" : "Banco"} · {c.nombre}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Fecha">
              <Input type="date" value={pago.fecha} onChange={(e) => setPago({ ...pago, fecha: e.target.value })} />
            </FormField>
            <FormField label="Valor">
              <Input type="number" value={pago.valor} onChange={(e) => setPago({ ...pago, valor: e.target.value })} />
            </FormField>
            <FormField label="Observaciones">
              <Input
                value={pago.observaciones}
                onChange={(e) => setPago({ ...pago, observaciones: e.target.value })}
              />
            </FormField>
          </>
        )}
      </Modal>
    </div>
  );
}
