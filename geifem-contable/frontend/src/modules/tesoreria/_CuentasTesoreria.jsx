import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

/**
 * Vista compartida de tesorería para cajas y cuentas bancarias.
 * tipo: "caja" | "banco"
 */
export default function CuentasTesoreria({ tipo, titulo, endpointCatalogo, endpointSaldos }) {
  const [cuentas, setCuentas] = useState([]);
  const [movimientos, setMovimientos] = useState([]);
  const [error, setError] = useState(null);
  const [openCuenta, setOpenCuenta] = useState(false);
  const [openMov, setOpenMov] = useState(false);
  const [cuenta, setCuenta] = useState({ nombre: "", saldo_inicial: 0 });
  const [mov, setMov] = useState({
    cuenta_id: "",
    tipo: "ingreso",
    fecha: new Date().toISOString().slice(0, 10),
    valor: 0,
    concepto: "",
    cuenta_contrapartida: "",
  });

  const cargar = async () => {
    try {
      const [c, m] = await Promise.all([
        api.get(endpointSaldos),
        api.get(`/api/tesoreria/movimientos?cuenta_tipo=${tipo}`),
      ]);
      setCuentas(c.data);
      setMovimientos(m.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo]);

  const guardarCuenta = async () => {
    try {
      await api.post(endpointCatalogo, {
        ...cuenta,
        saldo_inicial: Number(cuenta.saldo_inicial || 0),
      });
      setOpenCuenta(false);
      setCuenta({ nombre: "", saldo_inicial: 0 });
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const guardarMov = async () => {
    try {
      await api.post("/api/tesoreria/movimientos", {
        ...mov,
        cuenta_tipo: tipo,
        valor: Number(mov.valor),
        cuenta_contrapartida: mov.cuenta_contrapartida || null,
      });
      setOpenMov(false);
      setMov({ ...mov, valor: 0, concepto: "" });
      cargar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">{titulo}</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setOpenCuenta(true)}
            className="border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded"
          >
            + Cuenta
          </button>
          <button
            onClick={() => setOpenMov(true)}
            className="bg-geifem-navy text-white text-sm px-3 py-2 rounded"
          >
            + Movimiento
          </button>
        </div>
      </div>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <Table
        columns={[
          { key: "nombre", label: "Cuenta" },
          ...(tipo === "banco"
            ? [
                { key: "banco", label: "Banco" },
                { key: "numero_cuenta", label: "N° cuenta" },
              ]
            : []),
          { key: "saldo_inicial", label: "Saldo inicial", render: (r) => fmtCOP(r.saldo_inicial || 0) },
          { key: "saldo", label: "Saldo actual", render: (r) => fmtCOP(r.saldo) },
        ]}
        rows={cuentas}
        empty="Sin cuentas registradas"
      />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Movimientos</h2>
      <Table
        columns={[
          { key: "fecha", label: "Fecha" },
          { key: "referencia", label: "Documento" },
          { key: "cuenta_nombre", label: "Cuenta" },
          { key: "concepto", label: "Concepto" },
          { key: "tipo", label: "Tipo" },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
        ]}
        rows={movimientos}
        empty="Sin movimientos"
      />

      <Modal
        open={openCuenta}
        onClose={() => setOpenCuenta(false)}
        title={`Nueva cuenta — ${titulo}`}
        footer={
          <>
            <button onClick={() => setOpenCuenta(false)} className="px-3 py-1.5 rounded border border-slate-300 text-sm">
              Cancelar
            </button>
            <button onClick={guardarCuenta} className="px-3 py-1.5 rounded bg-geifem-navy text-white text-sm">
              Guardar
            </button>
          </>
        }
      >
        <FormField label="Nombre">
          <Input value={cuenta.nombre} onChange={(e) => setCuenta({ ...cuenta, nombre: e.target.value })} />
        </FormField>
        {tipo === "banco" && (
          <>
            <FormField label="Banco">
              <Input value={cuenta.banco || ""} onChange={(e) => setCuenta({ ...cuenta, banco: e.target.value })} />
            </FormField>
            <FormField label="Número de cuenta">
              <Input
                value={cuenta.numero_cuenta || ""}
                onChange={(e) => setCuenta({ ...cuenta, numero_cuenta: e.target.value })}
              />
            </FormField>
          </>
        )}
        <FormField label="Saldo inicial">
          <Input
            type="number"
            value={cuenta.saldo_inicial}
            onChange={(e) => setCuenta({ ...cuenta, saldo_inicial: e.target.value })}
          />
        </FormField>
      </Modal>

      <Modal
        open={openMov}
        onClose={() => setOpenMov(false)}
        title="Nuevo movimiento de tesorería"
        footer={
          <>
            <button onClick={() => setOpenMov(false)} className="px-3 py-1.5 rounded border border-slate-300 text-sm">
              Cancelar
            </button>
            <button onClick={guardarMov} className="px-3 py-1.5 rounded bg-geifem-navy text-white text-sm">
              Registrar
            </button>
          </>
        }
      >
        <FormField label="Cuenta">
          <Select value={mov.cuenta_id} onChange={(e) => setMov({ ...mov, cuenta_id: e.target.value })}>
            <option value="">Seleccione…</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Tipo">
          <Select value={mov.tipo} onChange={(e) => setMov({ ...mov, tipo: e.target.value })}>
            <option value="ingreso">Ingreso</option>
            <option value="egreso">Egreso</option>
          </Select>
        </FormField>
        <FormField label="Fecha">
          <Input type="date" value={mov.fecha} onChange={(e) => setMov({ ...mov, fecha: e.target.value })} />
        </FormField>
        <FormField label="Valor">
          <Input type="number" value={mov.valor} onChange={(e) => setMov({ ...mov, valor: e.target.value })} />
        </FormField>
        <FormField label="Concepto">
          <Input value={mov.concepto} onChange={(e) => setMov({ ...mov, concepto: e.target.value })} />
        </FormField>
        <FormField label="Cuenta contrapartida (código PUC)" hint="Ej.: 4135 ingresos, 5195 gastos">
          <Input
            value={mov.cuenta_contrapartida}
            onChange={(e) => setMov({ ...mov, cuenta_contrapartida: e.target.value })}
          />
        </FormField>
      </Modal>
    </div>
  );
}
