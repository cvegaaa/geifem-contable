import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
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

export default function Page() {
  const [cartera, setCartera] = useState({ cxc: [], cxp: [], resumen: {} });
  const [cuentas, setCuentas] = useState([]);
  const [pagos, setPagos] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [doc, setDoc] = useState(null);
  // Pago existente que se está editando (null = pago nuevo).
  const [editando, setEditando] = useState(null);
  const [pago, setPago] = useState({
    cuenta_tipo: "caja",
    cuenta_id: "",
    fecha: hoy(),
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
      setError(mensajeError(e));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Pago anulado: se restableció el saldo de la factura");
    cargar();
  });

  useEffect(() => {
    cargar();
  }, []);

  const abrirCruce = (d) => {
    setEditando(null);
    setDoc(d);
    setPago({ ...pago, fecha: hoy(), valor: d.saldo, cuenta_id: "", observaciones: "" });
  };

  const editarPago = (p) => {
    setEditando(p);
    setDoc({
      id: p.documento_id,
      tipo: p.documento_tipo,
      documento: p.documento_numero,
      tercero: p.tercero_nombre,
      saldo: Number(p.saldo_resultante || 0) + Number(p.valor),
    });
    setPago({ cuenta_tipo: p.cuenta_tipo, cuenta_id: p.cuenta_id, fecha: p.fecha, valor: p.valor, observaciones: p.observaciones || "" });
  };

  const registrarPago = async () => {
    setError(null);
    const cuenta = cuentas.find((c) => c.id === pago.cuenta_id);
    if (!cuenta) return setError("Selecciona la cuenta de caja o banco");
    try {
      const cuerpo = {
        documento_tipo: doc.tipo,
        documento_id: doc.id,
        cuenta_tipo: cuenta.tipo,
        cuenta_id: cuenta.id,
        fecha: pago.fecha,
        valor: Number(pago.valor),
        observaciones: pago.observaciones || null,
      };
      const { data } = editando
        ? await api.put(`/api/tesoreria/pagos/${editando.id}`, cuerpo)
        : await api.post("/api/tesoreria/pagos", cuerpo);
      setMensaje(
        `${numeroDoc(data)} ${editando ? "actualizado" : "aplicado"} a ${data.documento_numero} — saldo restante ${fmtCOP(
          data.saldo_resultante
        )}`
      );
      setDoc(null);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  const columnas = [
    { key: "fecha", label: "Fecha" },
    { key: "vencimiento", label: "Vence", render: (r) => r.vencimiento || "—" },
    { key: "documento", label: "Documento" },
    { key: "tercero", label: "Tercero" },
    { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
    { key: "saldo", label: "Saldo", render: (r) => fmtCOP(r.saldo) },
    {
      key: "_acc",
      label: "Acciones",
      render: (r) => (
        <button onClick={() => abrirCruce(r)} className="text-xs text-geifem-blue hover:underline">
          {r.tipo === "cxc" ? "Registrar cobro" : "Registrar pago"}
        </button>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Cartera y pagos</h1>
      <p className="text-slate-500 text-sm mb-4">
        Cruza recaudos y pagos contra facturas; cada cruce genera movimiento de tesorería y asiento
        contable.
      </p>
      <Avisos error={error} mensaje={mensaje} />

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
      <Table titulo="Cuentas por cobrar" columns={columnas} rows={cartera.cxc} empty="Sin cartera pendiente" />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Cuentas por pagar</h2>
      <Table titulo="Cuentas por pagar" columns={columnas} rows={cartera.cxp} empty="Sin obligaciones pendientes" />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Pagos y recaudos aplicados</h2>
      <Table titulo="Pagos y recaudos"
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r) || r.referencia}</span> },
          { key: "fecha", label: "Fecha" },
          { key: "documento_numero", label: "Aplica a" },
          { key: "tercero_nombre", label: "Tercero" },
          { key: "cuenta_nombre", label: "Caja / banco" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acciones",
            label: "",
            render: (r) => (
              <AccionesDocumento
                tipoDoc="pago"
                doc={r}
                modulo="tesoreria"
                onEditar={editarPago}
                onAnular={(d) => anulacion.pedir(d, `/api/tesoreria/pagos/${d.id}/anular`)}
              />
            ),
          },
        ]}
        rows={pagos}
        empty="Sin cruces registrados"
      />

      <Modal
        open={!!doc}
        onClose={() => setDoc(null)}
        title={doc ? `${editando ? `Editar ${numeroDoc(editando)}` : doc.tipo === "cxc" ? "Cobro" : "Pago"} — ${doc.documento}` : ""}
        footer={
          <>
            <button onClick={() => setDoc(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">
              Cancelar
            </button>
            <button onClick={registrarPago} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">
              {editando ? "Guardar cambios" : "Aplicar"}
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
      {anulacion.modal}
    </div>
  );
}
