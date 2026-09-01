import { useEffect, useMemo, useState } from "react";
import api from "../../../core/api.js";
import Table from "../../../shared/layout/Table/index.jsx";
import Modal from "../../../shared/layout/Modal/index.jsx";
import FormField, { Input, Select } from "../../../shared/layout/FormField/index.jsx";

const fmtCOP = (n) =>
  n == null ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

const EJEMPLO = "2026-08-01;Consignación cliente ACME;1500000\n2026-08-03;Pago proveedor XYZ;-450000";

export default function Page() {
  const [cuentas, setCuentas] = useState([]);
  const [cuentaId, setCuentaId] = useState("");
  const [tolerancia, setTolerancia] = useState(3);
  const [resultado, setResultado] = useState(null);
  const [seleccion, setSeleccion] = useState({});
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [openExtracto, setOpenExtracto] = useState(false);
  const [texto, setTexto] = useState("");

  useEffect(() => {
    api
      .get("/api/tesoreria/bancos")
      .then(({ data }) => {
        setCuentas(data);
        if (data.length) setCuentaId(data[0].id);
      })
      .catch((e) => setError(e.response?.data?.detail || e.message));
  }, []);

  const conciliar = async () => {
    setError(null);
    setMensaje(null);
    setCargando(true);
    try {
      const { data } = await api.get(
        `/api/tesoreria/conciliacion-bancaria-auto?cuenta_id=${cuentaId}&tolerancia_dias=${tolerancia}`
      );
      setResultado(data);
      setSeleccion(Object.fromEntries(data.conciliados.map((c) => [c.extracto_id, true])));
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setCargando(false);
    }
  };

  const cargarExtracto = async () => {
    setError(null);
    try {
      const lineas = texto
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((l) => {
          const [fecha, descripcion, valor] = l.split(";");
          return {
            fecha: (fecha || "").trim(),
            descripcion: (descripcion || "").trim(),
            valor: Number((valor || "0").trim()),
          };
        });
      await api.post("/api/tesoreria/conciliacion/extracto", { cuenta_id: cuentaId, lineas });
      setOpenExtracto(false);
      setTexto("");
      setMensaje(`Extracto cargado (${lineas.length} líneas)`);
      conciliar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const confirmar = async () => {
    setError(null);
    try {
      const pares = (resultado?.conciliados || [])
        .filter((c) => seleccion[c.extracto_id])
        .map((c) => ({ extracto_id: c.extracto_id, movimiento_id: c.movimiento_id }));
      if (!pares.length) return;
      const { data } = await api.post("/api/tesoreria/conciliacion/confirmar", {
        cuenta_id: cuentaId,
        pares,
      });
      setMensaje(`${data.conciliados} partidas conciliadas`);
      conciliar();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const seleccionados = useMemo(
    () => (resultado?.conciliados || []).filter((c) => seleccion[c.extracto_id]).length,
    [resultado, seleccion]
  );

  return (
    <div>
      <h1 className="text-2xl font-bold text-geifem-navy">Conciliación bancaria automática</h1>
      <p className="text-slate-500 mb-4">
        Cruza las líneas del extracto contra los movimientos del libro por valor, signo y fecha.
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <FormField label="Cuenta bancaria">
          <Select value={cuentaId} onChange={(e) => setCuentaId(e.target.value)}>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre} {c.banco ? `— ${c.banco}` : ""}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Tolerancia (días)">
          <Input
            type="number"
            min={0}
            max={15}
            value={tolerancia}
            onChange={(e) => setTolerancia(Number(e.target.value || 0))}
          />
        </FormField>
        <button
          onClick={() => setOpenExtracto(true)}
          disabled={!cuentaId}
          className="px-3 py-2 rounded border border-slate-300 text-sm disabled:opacity-50"
        >
          Cargar extracto
        </button>
        <button
          onClick={conciliar}
          disabled={!cuentaId || cargando}
          className="px-4 py-2 rounded bg-geifem-navy text-white text-sm disabled:opacity-50"
        >
          {cargando ? "Conciliando…" : "Conciliar"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm mb-3">{error}</div>}
      {mensaje && <div className="text-green-700 text-sm mb-3">{mensaje}</div>}

      {resultado && (
        <>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5 mb-4">
            {Object.entries(resultado.resumen).map(([k, v]) => (
              <div key={k} className="bg-white border border-slate-200 rounded-lg p-3">
                <p className="text-xs uppercase text-slate-500">{k.replace(/_/g, " ")}</p>
                <p className="text-lg font-semibold text-geifem-navy">{v}</p>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-700">Partidas cruzadas</h2>
            <button
              onClick={confirmar}
              disabled={!seleccionados}
              className="px-3 py-1.5 rounded bg-geifem-gold text-geifem-navy text-sm font-semibold disabled:opacity-50"
            >
              Confirmar {seleccionados || ""}
            </button>
          </div>
          <Table
            columns={[
              {
                key: "sel",
                label: "",
                render: (r) => (
                  <input
                    type="checkbox"
                    checked={!!seleccion[r.extracto_id]}
                    onChange={(e) =>
                      setSeleccion({ ...seleccion, [r.extracto_id]: e.target.checked })
                    }
                  />
                ),
              },
              { key: "fecha_extracto", label: "Fecha extracto" },
              { key: "descripcion", label: "Descripción extracto" },
              { key: "fecha_libro", label: "Fecha libro" },
              { key: "concepto", label: "Concepto libro" },
              { key: "referencia", label: "Documento" },
              { key: "tipo", label: "Tipo" },
              { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
              { key: "confianza", label: "Confianza" },
            ]}
            rows={resultado.conciliados}
            empty="Sin coincidencias automáticas"
          />

          <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">
            Extracto sin conciliar
          </h2>
          <Table
            columns={[
              { key: "fecha", label: "Fecha" },
              { key: "descripcion", label: "Descripción" },
              { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
            ]}
            rows={resultado.extracto_sin_conciliar}
            empty="Todo el extracto quedó cruzado"
          />

          <h2 className="text-sm font-semibold text-slate-700 mt-6 mb-2">Libro sin conciliar</h2>
          <Table
            columns={[
              { key: "fecha", label: "Fecha" },
              { key: "referencia", label: "Documento" },
              { key: "concepto", label: "Concepto" },
              { key: "tipo", label: "Tipo" },
              { key: "valor", label: "Valor", render: (r) => fmtCOP(r.valor) },
            ]}
            rows={resultado.libro_sin_conciliar}
            empty="Todos los movimientos quedaron cruzados"
          />
        </>
      )}

      <Modal
        open={openExtracto}
        onClose={() => setOpenExtracto(false)}
        title="Cargar extracto bancario"
        footer={
          <>
            <button
              onClick={() => setOpenExtracto(false)}
              className="px-3 py-1.5 rounded border border-slate-300 text-sm"
            >
              Cancelar
            </button>
            <button
              onClick={cargarExtracto}
              className="px-3 py-1.5 rounded bg-geifem-navy text-white text-sm"
            >
              Cargar
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-500 mb-2">
          Pega una línea por movimiento con el formato{" "}
          <span className="font-mono">fecha;descripción;valor</span>. Valor positivo = consignación,
          negativo = retiro.
        </p>
        <textarea
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          rows={10}
          placeholder={EJEMPLO}
          className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
        />
      </Modal>
    </div>
  );
}
