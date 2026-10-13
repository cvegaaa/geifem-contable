import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, fmtCOP, hoy, mensajeError } from "../../../shared/documentos/index.jsx";

export default function Page() {
  const [tipo, setTipo] = useState("cxc");
  const [corte, setCorte] = useState(hoy());
  const [datos, setDatos] = useState(null);
  const [cuenta, setCuenta] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    api
      .get("/api/tesoreria/cartera/antiguedad", { params: { tipo, corte } })
      .then((r) => setDatos(r.data))
      .catch((e) => setError(mensajeError(e)));
  }, [tipo, corte]);

  const verEstado = async (fila) => {
    try {
      const { data } = await api.get("/api/tesoreria/cartera/estado-cuenta", { params: { tercero_id: fila.tercero_id, tipo } });
      setCuenta(data);
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  const columnas = [
    { key: "tercero", label: "Tercero" },
    { key: "documentos", label: "Docs." },
    ...(datos?.tramos || []).map((t) => ({
      key: t.clave,
      label: t.etiqueta,
      render: (r) => (r[t.clave] ? fmtCOP(r[t.clave]) : "—"),
    })),
    { key: "total", label: "Total", render: (r) => <b>{fmtCOP(r.total)}</b> },
    {
      key: "_acc",
      label: "",
      render: (r) =>
        r.tercero_id && (
          <button onClick={() => verEstado(r)} className="text-xs text-geifem-blue hover:underline whitespace-nowrap">
            Estado de cuenta
          </button>
        ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Antigüedad de cartera</h1>
      <p className="text-sm text-slate-500 mb-4">Saldo pendiente por tercero según los días de mora a la fecha de corte (contados desde el vencimiento).</p>
      <Avisos error={error} />
      <div className="flex flex-wrap gap-3 mb-3">
        <FormField label="Cartera">
          <Select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="cxc">Por cobrar (clientes)</option>
            <option value="cxp">Por pagar (proveedores)</option>
          </Select>
        </FormField>
        <FormField label="Fecha de corte">
          <Input type="date" value={corte} onChange={(e) => setCorte(e.target.value)} />
        </FormField>
      </div>
      <Table
        titulo={`Antigüedad de cartera ${tipo === "cxc" ? "por cobrar" : "por pagar"} al ${corte}`}
        columns={columnas}
        rows={(datos?.filas || []).map((f, i) => ({ ...f, id: f.tercero_id || i }))}
        empty="No hay saldos pendientes"
        resumen={datos?.filas?.length ? { "Total cartera": datos.totales.total, "Vencida más de 90 días": datos.totales.d90_mas } : undefined}
      />

      <Modal
        open={Boolean(cuenta)}
        onClose={() => setCuenta(null)}
        title={cuenta ? `Estado de cuenta — ${cuenta.tercero}` : ""}
        ancho="max-w-3xl"
        footer={<button onClick={() => window.print()} className="px-3 py-1.5 text-sm rounded-sm border border-slate-300">Imprimir</button>}
      >
        {cuenta && (
          <>
            <p className="text-sm text-slate-500 mb-2">Documento {cuenta.documento || "—"}</p>
            <div className="grid grid-cols-3 gap-2 mb-3 text-sm">
              <div className="bg-slate-50 rounded p-2">Facturado<br /><b>{fmtCOP(cuenta.resumen.facturado)}</b></div>
              <div className="bg-slate-50 rounded p-2">Pagado<br /><b>{fmtCOP(cuenta.resumen.pagado)}</b></div>
              <div className="bg-slate-50 rounded p-2">Saldo<br /><b>{fmtCOP(cuenta.resumen.saldo)}</b></div>
            </div>
            <Table
              titulo={`Facturas de ${cuenta.tercero}`}
              columns={[
                { key: "documento", label: "Factura" },
                { key: "fecha", label: "Fecha" },
                { key: "vencimiento", label: "Vence", render: (r) => r.vencimiento || "—" },
                { key: "total", label: "Total", render: (r) => fmtCOP(r.total) },
                { key: "saldo", label: "Saldo", render: (r) => fmtCOP(r.saldo) },
                { key: "estado", label: "Estado" },
              ]}
              rows={cuenta.facturas}
              porPagina={10}
            />
            {cuenta.pagos.length > 0 && (
              <>
                <h4 className="text-sm font-semibold mt-3 mb-1">Pagos aplicados</h4>
                <Table
                  titulo={`Pagos de ${cuenta.tercero}`}
                  columns={[
                    { key: "numero", label: "Número" },
                    { key: "fecha", label: "Fecha" },
                    { key: "documento", label: "Factura" },
                    { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
                  ]}
                  rows={cuenta.pagos}
                  porPagina={10}
                />
              </>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
