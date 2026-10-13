import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";

const NOMBRES_DOCUMENTO = {
  comprobante: "Comprobante contable",
  factura: "Factura de venta",
  pos: "Documento POS",
  nota: "Nota crédito/débito",
  orden_compra: "Orden de compra",
  recepcion: "Entrada de mercancía",
  factura_proveedor: "Factura de proveedor",
  movimiento_tesoreria: "Movimiento de caja/banco",
  pago: "Recibo / egreso",
  ajuste_inventario: "Ajuste de inventario",
  nomina_periodo: "Liquidación de nómina",
  pago_nomina: "Pago de nómina",
  pago_obligacion: "Pago de prestaciones / aportes",
  nomina_liquidacion_final: "Liquidación de contrato",
  saldo_inicial: "Saldo inicial",
  cuenta_caja: "Caja",
  cuenta_banco: "Cuenta bancaria",
};

export default function Page() {
  const [rows, setRows] = useState([]);
  const [usuarios, setUsuarios] = useState({});
  const [tipo, setTipo] = useState("");

  useEffect(() => {
    const q = tipo ? `?documento_tipo=${tipo}` : "";
    api.get(`/api/contabilidad/auditoria${q}`).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [tipo]);

  useEffect(() => {
    api
      .get("/api/configuracion/usuarios-roles")
      .then((r) => setUsuarios(Object.fromEntries(r.data.map((u) => [u.id, u.nombre]))))
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Auditoría</h1>
      <p className="text-sm text-slate-500 mb-3">
        Historial de solo lectura: quién creó, editó o anuló cada documento (últimos 500 eventos).
      </p>
      <select
        value={tipo}
        onChange={(e) => setTipo(e.target.value)}
        className="border border-slate-300 rounded-sm px-2 py-1.5 text-sm mb-3 bg-white"
      >
        <option value="">Todos los documentos</option>
        {Object.entries(NOMBRES_DOCUMENTO).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>
      <Table
        columns={[
          { key: "fecha_hora", label: "Fecha y hora", render: (r) => new Date(r.fecha_hora).toLocaleString("es-CO") },
          { key: "documento_tipo", label: "Documento", render: (r) => NOMBRES_DOCUMENTO[r.documento_tipo] || r.documento_tipo },
          { key: "numero", label: "Número" },
          { key: "accion", label: "Acción", render: (r) => <span className="capitalize">{r.accion}</span> },
          { key: "usuario_id", label: "Usuario", render: (r) => usuarios[r.usuario_id] || "—" },
          { key: "detalle", label: "Motivo", render: (r) => r.detalle?.motivo || "" },
        ]}
        rows={rows}
        empty="Sin eventos registrados"
      />
    </div>
  );
}
