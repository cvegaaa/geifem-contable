import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../../core/api.js";
import { useAuth } from "../../shared/auth/AuthContext.jsx";
import Table from "../../shared/layout/Table/index.jsx";
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

const lineaVacia = () => ({ cuenta_puc_id: "", tercero_id: "", descripcion: "", debito: "", credito: "" });

/** Pantalla de un tipo de comprobante: listado + formulario (nuevo / editar / duplicar). */
export default function ComprobanteForm({ tipo, titulo }) {
  const { puede } = useAuth();
  const [params, setParams] = useSearchParams();
  const [lista, setLista] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [terceros, setTerceros] = useState([]);
  const [modo, setModo] = useState(null); // null | nuevo | editar | duplicar
  const [origen, setOrigen] = useState(null);
  const [fecha, setFecha] = useState(hoy());
  const [descripcion, setDescripcion] = useState("");
  const [terceroId, setTerceroId] = useState("");
  const [lineas, setLineas] = useState([lineaVacia(), lineaVacia()]);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = async () => {
    try {
      const { data } = await api.get(`/api/contabilidad/comprobantes?tipo=${tipo}`);
      setLista(data);
    } catch (err) {
      setError(mensajeError(err));
    }
  };

  const anulacion = useAnulacion(() => {
    setMensaje("Comprobante anulado");
    cargar();
  });

  useEffect(() => {
    cargar();
    api.get("/api/configuracion/plan-cuentas").then((r) => setCuentas(r.data)).catch(() => {});
    api.get("/api/configuracion/terceros").then((r) => setTerceros(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo]);

  // Permite abrir el formulario desde "Consulta de comprobantes" (?editar=id / ?duplicar=id).
  useEffect(() => {
    const id = params.get("editar") || params.get("duplicar");
    if (!id) return;
    const m = params.get("editar") ? "editar" : "duplicar";
    api
      .get(`/api/contabilidad/comprobantes/${id}`)
      .then((r) => abrir(m, r.data))
      .catch((err) => setError(mensajeError(err)))
      .finally(() => setParams({}, { replace: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const abrir = (m, doc = null) => {
    setModo(m);
    setOrigen(doc);
    setError(null);
    setMensaje(null);
    if (doc) {
      setFecha(m === "duplicar" ? hoy() : doc.fecha);
      setDescripcion(doc.descripcion || "");
      setTerceroId(doc.tercero_id || "");
      setLineas(
        doc.lineas.map((l) => ({
          cuenta_puc_id: l.cuenta_puc_id,
          tercero_id: l.tercero_id || "",
          descripcion: l.descripcion || "",
          debito: l.debito || "",
          credito: l.credito || "",
        }))
      );
    } else {
      setFecha(hoy());
      setDescripcion("");
      setTerceroId("");
      setLineas([lineaVacia(), lineaVacia()]);
    }
  };

  const totalDeb = lineas.reduce((s, l) => s + Number(l.debito || 0), 0);
  const totalCre = lineas.reduce((s, l) => s + Number(l.credito || 0), 0);
  const cuadrado = Math.round(totalDeb * 100) === Math.round(totalCre * 100) && totalDeb > 0;

  const actualizar = (i, campo, valor) => {
    setLineas((ls) =>
      ls.map((l, idx) => {
        if (idx !== i) return l;
        const nueva = { ...l, [campo]: valor };
        // Una línea lleva valor en débito o en crédito, no en ambos.
        if (campo === "debito" && valor) nueva.credito = "";
        if (campo === "credito" && valor) nueva.debito = "";
        return nueva;
      })
    );
  };

  const guardar = async (estado) => {
    setError(null);
    if (lineas.some((l) => !l.cuenta_puc_id)) return setError("Selecciona la cuenta de cada línea");
    if (lineas.some((l) => !Number(l.debito) && !Number(l.credito)))
      return setError("Cada línea debe tener valor en débito o en crédito");
    const cuerpo = {
      tipo,
      fecha,
      descripcion: descripcion || null,
      tercero_id: terceroId || null,
      estado,
      lineas: lineas.map((l) => ({
        cuenta_puc_id: l.cuenta_puc_id,
        tercero_id: l.tercero_id || null,
        descripcion: l.descripcion || null,
        debito: Number(l.debito || 0),
        credito: Number(l.credito || 0),
      })),
    };
    setGuardando(true);
    try {
      const { data } =
        modo === "editar"
          ? await api.put(`/api/contabilidad/comprobantes/${origen.id}`, cuerpo)
          : await api.post("/api/contabilidad/comprobantes", cuerpo);
      setMensaje(`Comprobante ${data.numero} ${modo === "editar" ? "actualizado" : "guardado"} (${data.estado})`);
      setModo(null);
      cargar();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  };

  const columnas = [
    { key: "numero", label: "Número", render: (r) => <span className="font-medium">{numeroDoc(r)}</span> },
    { key: "fecha", label: "Fecha" },
    { key: "descripcion", label: "Descripción" },
    {
      key: "total",
      label: "Valor",
      render: (r) => fmtCOP(r.lineas?.reduce((s, l) => s + Number(l.debito || 0), 0)),
    },
    { key: "estado", label: "Estado", render: (r) => <EstadoBadge estado={r.estado} /> },
    {
      key: "_acciones",
      label: "",
      render: (r) => (
        <AccionesDocumento
          tipoDoc="comprobante"
          doc={r}
          modulo="contabilidad"
          onEditar={(d) => abrir("editar", d)}
          onDuplicar={(d) => abrir("duplicar", d)}
          onAnular={(d) => anulacion.pedir(d, `/api/contabilidad/comprobantes/${d.id}/anular`)}
        />
      ),
    },
  ];

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-geifem-navy">{titulo}</h1>
        {puede("contabilidad", "crear") && !modo && (
          <button onClick={() => abrir("nuevo")} className="bg-geifem-navy text-white text-sm px-4 py-2 rounded-sm hover:bg-geifem-blue">
            + Nuevo comprobante
          </button>
        )}
      </div>
      <Avisos error={error} mensaje={mensaje} />

      {modo && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
          <h2 className="text-lg font-bold text-geifem-navy mb-1">{tituloModo(modo, "comprobante", origen)}</h2>
          <p className="text-xs text-slate-500 mb-4">
            {modo === "editar" ? "Conserva su número." : "El número se asigna automáticamente al guardar."}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <FormField label="Fecha">
              <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </FormField>
            <FormField label="Tercero (opcional)">
              <Select value={terceroId} onChange={(e) => setTerceroId(e.target.value)}>
                <option value="">Sin tercero</option>
                {terceros.map((t) => (
                  <option key={t.id} value={t.id}>{t.nombre}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="Descripción">
              <Input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            </FormField>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-x-auto mt-2">
            <table className="w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="text-left px-3 py-2 min-w-64">Cuenta</th>
                  <th className="text-left px-3 py-2">Detalle</th>
                  <th className="text-right px-3 py-2 w-36">Débito</th>
                  <th className="text-right px-3 py-2 w-36">Crédito</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {lineas.map((l, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1">
                      <SelectorCuenta cuentas={cuentas} value={l.cuenta_puc_id} onChange={(v) => actualizar(i, "cuenta_puc_id", v)} />
                    </td>
                    <td className="px-2 py-1">
                      <Input value={l.descripcion} onChange={(e) => actualizar(i, "descripcion", e.target.value)} />
                    </td>
                    <td className="px-2 py-1">
                      <Input type="number" min="0" className="text-right" value={l.debito} onChange={(e) => actualizar(i, "debito", e.target.value)} />
                    </td>
                    <td className="px-2 py-1">
                      <Input type="number" min="0" className="text-right" value={l.credito} onChange={(e) => actualizar(i, "credito", e.target.value)} />
                    </td>
                    <td className="text-center">
                      <button
                        onClick={() => setLineas((ls) => ls.filter((_, idx) => idx !== i))}
                        disabled={lineas.length <= 2}
                        className="text-red-500 text-xs disabled:opacity-30"
                        title="Quitar línea"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50">
                <tr>
                  <td colSpan={2} className="px-3 py-2 text-right font-semibold">
                    Totales {cuadrado ? "" : <span className="text-red-600 font-normal">(descuadrado: {fmtCOP(totalDeb - totalCre)})</span>}
                  </td>
                  <td className="px-3 py-2 text-right">{fmtCOP(totalDeb)}</td>
                  <td className="px-3 py-2 text-right">{fmtCOP(totalCre)}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            <button onClick={() => setLineas([...lineas, lineaVacia()])} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">
              + Línea
            </button>
            <button onClick={() => guardar("borrador")} disabled={guardando} className="text-sm px-3 py-1.5 rounded-sm bg-slate-200 disabled:opacity-50">
              Guardar borrador
            </button>
            <button
              onClick={() => guardar("contabilizado")}
              disabled={!cuadrado || guardando}
              className="text-sm px-3 py-1.5 rounded-sm bg-geifem-navy text-white disabled:opacity-50"
            >
              Contabilizar
            </button>
            <button onClick={() => setModo(null)} className="text-sm px-3 py-1.5 rounded-sm border border-slate-300">
              Cancelar
            </button>
          </div>
        </div>
      )}

      <Table columns={columnas} rows={lista} empty="Aún no hay comprobantes de este tipo" />
      {anulacion.modal}
    </div>
  );
}
