import { useEffect, useState } from "react";
import api from "../../core/api.js";
import { useAuth } from "../../shared/auth/AuthContext.jsx";
import Table from "../../shared/layout/Table/index.jsx";
import Modal from "../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../shared/layout/FormField/index.jsx";
import {
  AccionesDocumento,
  Avisos,
  EstadoBadge,
  SelectorCuenta,
  fmtCOP,
  hoy,
  mensajeError,
  numeroDoc,
  tituloModo,
  useAnulacion,
} from "../../shared/documentos/index.jsx";

const movVacio = () => ({
  cuenta_id: "",
  tipo: "ingreso",
  fecha: hoy(),
  valor: "",
  concepto: "",
  tercero_id: "",
  cuenta_contrapartida: "",
});

/**
 * Vista compartida de tesorería para cajas y cuentas bancarias.
 * tipo: "caja" | "banco"
 */
export default function CuentasTesoreria({ tipo, titulo, endpointCatalogo, endpointSaldos }) {
  const { puede } = useAuth();
  const [cuentas, setCuentas] = useState([]);
  const [movimientos, setMovimientos] = useState([]);
  const [plan, setPlan] = useState([]);
  const [terceros, setTerceros] = useState([]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [openCuenta, setOpenCuenta] = useState(false);
  const cuentaVacia = () => ({ nombre: "", saldo_inicial: 0, cuenta_contable: tipo === "caja" ? "1105" : "1110" });
  const [cuenta, setCuenta] = useState(cuentaVacia());
  const [editandoCuenta, setEditandoCuenta] = useState(null);
  const [errorCuenta, setErrorCuenta] = useState(null);
  const [modo, setModo] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [mov, setMov] = useState(movVacio());
  const [errorMov, setErrorMov] = useState(null);

  const cargar = async () => {
    try {
      const [c, m] = await Promise.all([
        api.get(endpointSaldos),
        api.get(`/api/tesoreria/movimientos?cuenta_tipo=${tipo}`),
      ]);
      setCuentas(c.data);
      setMovimientos(m.data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Movimiento anulado");
    cargar();
  });

  useEffect(() => {
    cargar();
    api.get("/api/configuracion/plan-cuentas").then((r) => setPlan(r.data)).catch(() => {});
    api.get("/api/configuracion/terceros").then((r) => setTerceros(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo]);

  const abrirCuenta = (c = null) => {
    setEditandoCuenta(c);
    setErrorCuenta(null);
    setCuenta(
      c
        ? { nombre: c.nombre, banco: c.banco, numero_cuenta: c.numero_cuenta, saldo_inicial: c.saldo_inicial || 0,
            cuenta_contable: c.cuenta_contable || "" }
        : cuentaVacia()
    );
    setOpenCuenta(true);
  };

  const guardarCuenta = async () => {
    setErrorCuenta(null);
    if (!cuenta.nombre.trim()) return setErrorCuenta("Escribe el nombre");
    if (!cuenta.cuenta_contable) return setErrorCuenta("Selecciona la cuenta contable");
    const cuerpo = { ...cuenta, saldo_inicial: Number(cuenta.saldo_inicial || 0) };
    try {
      if (editandoCuenta) await api.put(`${endpointCatalogo}/${editandoCuenta.id}`, cuerpo);
      else await api.post(endpointCatalogo, cuerpo);
      setOpenCuenta(false);
      setMensaje(editandoCuenta ? "Cuenta actualizada" : "Cuenta creada");
      cargar();
    } catch (err) {
      setErrorCuenta(mensajeError(err));
    }
  };

  const nombreCuentaPuc = (codigo) => {
    const c = plan.find((x) => x.codigo === codigo);
    return c ? `${c.codigo} — ${c.nombre}` : codigo || "Por defecto";
  };

  const abrirMov = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setErrorMov(null);
    setMov(
      doc
        ? {
            cuenta_id: doc.cuenta_id,
            tipo: doc.tipo,
            fecha: m === "editar" ? doc.fecha : hoy(),
            valor: doc.valor,
            concepto: doc.concepto,
            tercero_id: doc.tercero_id || "",
            cuenta_contrapartida: doc.cuenta_contrapartida || "",
          }
        : { ...movVacio(), cuenta_id: cuentas.length === 1 ? cuentas[0].id : "" }
    );
  };

  const guardarMov = async () => {
    setErrorMov(null);
    if (!mov.cuenta_id) return setErrorMov("Selecciona la cuenta");
    if (!mov.cuenta_contrapartida) return setErrorMov("Selecciona la cuenta contrapartida");
    const cuerpo = {
      ...mov,
      cuenta_tipo: tipo,
      valor: Number(mov.valor),
      tercero_id: mov.tercero_id || null,
    };
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/tesoreria/movimientos/${origen.id}`, cuerpo)
          : await api.post("/api/tesoreria/movimientos", cuerpo);
      setMensaje(`Movimiento ${numeroDoc(data)} ${modo === "editar" ? "actualizado" : "registrado"}`);
      setModo(null);
      cargar();
    } catch (err) {
      setErrorMov(mensajeError(err));
    }
  };

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">{titulo}</h1>
        <div className="flex gap-2">
          {puede("tesoreria", "crear") && (
            <>
              <button onClick={() => abrirCuenta()} className="border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm">
                + {tipo === "caja" ? "Caja" : "Cuenta bancaria"}
              </button>
              <button onClick={() => abrirMov("nuevo")} disabled={!cuentas.length}
                className="bg-geifem-navy text-white text-sm px-3 py-2 rounded-sm disabled:opacity-50"
                title={cuentas.length ? "" : "Primero crea una cuenta"}>
                + Movimiento
              </button>
            </>
          )}
        </div>
      </div>
      <Avisos error={error} mensaje={mensaje} />

      <Table titulo="Cuentas"
        columns={[
          { key: "nombre", label: "Cuenta" },
          ...(tipo === "banco"
            ? [
                { key: "banco", label: "Banco" },
                { key: "numero_cuenta", label: "N° cuenta" },
              ]
            : []),
          { key: "cuenta_contable", label: "Cuenta contable", render: (r) => nombreCuentaPuc(r.cuenta_contable) },
          { key: "saldo_inicial", label: "Saldo inicial", render: (r) => fmtCOP(r.saldo_inicial || 0) },
          { key: "saldo", label: "Saldo actual", render: (r) => <b>{fmtCOP(r.saldo)}</b> },
          {
            key: "_editar",
            label: "",
            render: (r) =>
              puede("tesoreria", "editar") ? (
                <button onClick={() => abrirCuenta(r)} className="text-xs text-geifem-blue hover:underline">Editar</button>
              ) : null,
          },
        ]}
        rows={cuentas}
        empty={`Aún no tienes ${tipo === "caja" ? "cajas" : "cuentas bancarias"}`}
      />

      <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Movimientos</h2>
      <Table titulo="Movimientos"
        columns={[
          { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r) || r.referencia}</span> },
          { key: "fecha", label: "Fecha" },
          { key: "cuenta_nombre", label: "Cuenta" },
          { key: "concepto", label: "Concepto" },
          { key: "tipo", label: "Tipo", render: (r) => (r.tipo === "ingreso" ? "Ingreso" : "Egreso") },
          { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
          { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
          {
            key: "_acciones",
            label: "",
            render: (r) =>
              r.origen === "manual" ? (
                <AccionesDocumento
                  tipoDoc="movimiento"
                  doc={r}
                  modulo="tesoreria"
                  onEditar={(d) => abrirMov("editar", d)}
                  onDuplicar={(d) => abrirMov("duplicar", d)}
                  onAnular={(d) => anulacion.pedir(d, `/api/tesoreria/movimientos/${d.id}/anular`)}
                  bloqueo={r.conciliado ? "Conciliado con el extracto" : null}
                />
              ) : (
                <span className="text-[11px] text-slate-400">
                  {r.origen === "pos" ? "Desde Documento POS" : "Desde Cartera y pagos"}
                </span>
              ),
          },
        ]}
        rows={movimientos}
        empty="Sin movimientos"
      />

      <Modal
        open={openCuenta}
        onClose={() => setOpenCuenta(false)}
        title={`${editandoCuenta ? "Editar" : "Nueva"} ${tipo === "caja" ? "caja" : "cuenta bancaria"}`}
        footer={
          <>
            <button onClick={() => setOpenCuenta(false)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
            <button onClick={guardarCuenta} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">Guardar</button>
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
              <Input value={cuenta.numero_cuenta || ""} onChange={(e) => setCuenta({ ...cuenta, numero_cuenta: e.target.value })} />
            </FormField>
          </>
        )}
        <FormField label="Cuenta contable" hint="Cuenta del PUC donde se registran sus movimientos (crea subcuentas en Plan de cuentas, p. ej. 111005).">
          <SelectorCuenta cuentas={plan.filter((c) => c.codigo.startsWith("11"))} porCodigo value={cuenta.cuenta_contable}
            onChange={(v) => setCuenta({ ...cuenta, cuenta_contable: v })} />
        </FormField>
        <FormField label="Saldo inicial" hint="Genera su propio asiento: débito a la cuenta contable y crédito a la contrapartida de saldos iniciales (Parámetros contables).">
          <Input type="number" value={cuenta.saldo_inicial} onChange={(e) => setCuenta({ ...cuenta, saldo_inicial: e.target.value })} />
        </FormField>
        {errorCuenta && <p className="text-sm text-red-600">{errorCuenta}</p>}
      </Modal>

      <Modal
        open={Boolean(modo)}
        onClose={() => setModo(null)}
        title={tituloModo(modo, "movimiento", origen)}
        footer={
          <>
            <button onClick={() => setModo(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">Cancelar</button>
            <button onClick={guardarMov} className="px-3 py-1.5 rounded-sm bg-geifem-navy text-white text-sm">
              {modo === "editar" ? "Guardar cambios" : "Registrar"}
            </button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-x-3">
          <FormField label="Cuenta">
            <Select value={mov.cuenta_id} onChange={(e) => setMov({ ...mov, cuenta_id: e.target.value })}>
              <option value="">Seleccionar…</option>
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Tipo">
            <Select value={mov.tipo} onChange={(e) => setMov({ ...mov, tipo: e.target.value })}>
              <option value="ingreso">Ingreso (entra dinero)</option>
              <option value="egreso">Egreso (sale dinero)</option>
            </Select>
          </FormField>
          <FormField label="Fecha">
            <Input type="date" value={mov.fecha} onChange={(e) => setMov({ ...mov, fecha: e.target.value })} />
          </FormField>
          <FormField label="Valor">
            <Input type="number" min="0" value={mov.valor} onChange={(e) => setMov({ ...mov, valor: e.target.value })} />
          </FormField>
        </div>
        <FormField label="Concepto">
          <Input value={mov.concepto} onChange={(e) => setMov({ ...mov, concepto: e.target.value })} />
        </FormField>
        <FormField label="Tercero (opcional)">
          <Select value={mov.tercero_id} onChange={(e) => setMov({ ...mov, tercero_id: e.target.value })}>
            <option value="">Sin tercero</option>
            {terceros.map((t) => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </Select>
        </FormField>
        <FormField label="Cuenta contrapartida" hint="A qué cuenta contable va el ingreso o el gasto (p. ej. 4135 ventas, 5135 servicios).">
          <SelectorCuenta cuentas={plan} porCodigo value={mov.cuenta_contrapartida}
            onChange={(v) => setMov({ ...mov, cuenta_contrapartida: v })} />
        </FormField>
        {errorMov && <p className="text-sm text-red-600">{errorMov}</p>}
      </Modal>
      {anulacion.modal}
    </div>
  );
}
