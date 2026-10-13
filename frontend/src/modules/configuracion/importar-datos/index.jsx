import { useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import Table from "../../../shared/layout/Table/index.jsx";
import FormField, { Input } from "../../../shared/layout/FormField/index.jsx";
import { Avisos, fmtCOP, mensajeError } from "../../../shared/documentos/index.jsx";

const TIPOS = [
  {
    clave: "terceros", titulo: "Terceros", icono: "Clientes y proveedores",
    ayuda: "Nombre, documento, contacto y perfil tributario (régimen, retenciones). El documento no puede repetirse.",
  },
  {
    clave: "productos", titulo: "Productos y servicios", icono: "Catálogo",
    ayuda: "Código, nombre, precio e IVA. Las existencias iniciales se cargan con una entrada de mercancía.",
  },
  {
    clave: "saldos-iniciales", titulo: "Saldos iniciales", icono: "Apertura contable",
    ayuda: "Saldos por cuenta contable (con tercero opcional). Genera un comprobante de apertura contabilizado; debe cuadrar. Las líneas de clientes (débito) y proveedores (crédito) llevan tercero y número de factura, con fecha y vencimiento: así quedan como cuentas por cobrar y por pagar por documento.",
    conFecha: true,
  },
];

async function descargarPlantilla(clave) {
  const { data } = await api.get(`/api/importar/${clave}/plantilla`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `plantilla-${clave}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

function Tarjeta({ tipo }) {
  const { puede } = useAuth();
  const [archivo, setArchivo] = useState(null);
  const [fecha, setFecha] = useState(`${new Date().getFullYear()}-01-01`);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [trabajando, setTrabajando] = useState(false);

  const enviar = async (simular) => {
    setError(null);
    setTrabajando(true);
    try {
      const form = new FormData();
      form.append("archivo", archivo);
      const { data } = await api.post(`/api/importar/${tipo.clave}`, form, {
        params: { simular, ...(tipo.conFecha ? { fecha } : {}) },
      });
      setResultado(data);
    } catch (err) {
      setResultado(null);
      setError(mensajeError(err));
    } finally {
      setTrabajando(false);
    }
  };

  const listo = resultado && resultado.errores.length === 0 && resultado.validas > 0;

  return (
    <section className="bg-white border border-slate-200 rounded-lg p-4 mb-5">
      <h2 className="font-semibold text-geifem-navy">{tipo.titulo}</h2>
      <p className="text-sm text-slate-500 mb-3">{tipo.ayuda}</p>
      <div className="flex flex-wrap items-end gap-3">
        <button onClick={() => descargarPlantilla(tipo.clave)} className="mb-3 border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm">
          1. Descargar plantilla
        </button>
        <label className="mb-3 text-sm">
          <span className="block text-xs text-slate-500 mb-1">2. Archivo (.xlsx o .csv)</span>
          <input type="file" accept=".xlsx,.csv" onChange={(e) => { setArchivo(e.target.files[0] || null); setResultado(null); }} className="text-sm" />
        </label>
        {tipo.conFecha && (
          <FormField label="Fecha de apertura"><Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></FormField>
        )}
        <button onClick={() => enviar(true)} disabled={!archivo || trabajando} className="mb-3 bg-slate-700 text-white text-sm px-3 py-2 rounded-sm disabled:opacity-50">
          3. Validar
        </button>
        {puede("configuracion", "crear") && (
          <button onClick={() => enviar(false)} disabled={!listo || trabajando} className="mb-3 bg-geifem-navy text-white text-sm px-3 py-2 rounded-sm disabled:opacity-40"
            title={listo ? "" : "Primero valida el archivo sin errores"}>
            4. Importar
          </button>
        )}
      </div>
      <Avisos error={error} />
      {resultado && (
        <div className="mt-2">
          <p className={`text-sm mb-2 ${resultado.importado ? "text-emerald-700" : resultado.errores.length ? "text-red-600" : "text-slate-600"}`}>
            {resultado.importado
              ? `Importación completada: ${resultado.creados} registro(s)${resultado.detalle?.comprobante ? ` (comprobante ${resultado.detalle.comprobante})` : ""}.`
              : resultado.errores.length
                ? `El archivo tiene ${resultado.errores.length} error(es). No se guardó nada: corrígelo y vuelve a cargarlo.`
                : `Validación correcta: ${resultado.validas} fila(s) listas para importar.`}
            {resultado.detalle && !resultado.importado && ` Débitos ${fmtCOP(resultado.detalle.debitos)} · créditos ${fmtCOP(resultado.detalle.creditos)}.`}
          </p>
          {resultado.errores.length > 0 && (
            <Table
              titulo={`Errores de importación de ${tipo.titulo}`}
              columns={[{ key: "fila", label: "Fila", render: (e) => e.fila || "Total" }, { key: "mensaje", label: "Problema" }]}
              rows={resultado.errores.map((e, i) => ({ ...e, id: i }))}
            />
          )}
        </div>
      )}
    </section>
  );
}

export default function Page() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Importar datos</h1>
      <p className="text-sm text-slate-500 mb-4">
        Para empezar con tu información: descarga la plantilla, llénala en Excel, valida el archivo y, si no hay errores, impórtalo.
        La carga es todo o nada: si una fila falla, no se guarda ninguna. Orden recomendado: terceros, productos y al final los saldos iniciales.
      </p>
      {TIPOS.map((t) => <Tarjeta key={t.clave} tipo={t} />)}
    </div>
  );
}
