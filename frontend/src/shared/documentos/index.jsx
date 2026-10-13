import { useMemo, useState } from "react";
import api from "../../core/api.js";
import { useVistaDocumento } from "./Imprimible.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import Modal from "../layout/Modal/index.jsx";
import FormField, { Input } from "../layout/FormField/index.jsx";

export const hoy = () => new Date().toISOString().slice(0, 10);

export const fmtCOP = (n) =>
  n == null || n === "" ? "" : "$" + Number(n).toLocaleString("es-CO", { maximumFractionDigits: 2 });

export const mensajeError = (err) => err?.response?.data?.detail || err?.message || "Error inesperado";

/** Número visible del documento (los antiguos sin `numero` usan prefijo + consecutivo). */
export const numeroDoc = (d) => d?.numero || `${d?.prefijo || ""}${d?.consecutivo ?? ""}`;

const ESTILOS_ESTADO = {
  anulado: "bg-red-50 text-red-700 border-red-200",
  borrador: "bg-amber-50 text-amber-700 border-amber-200",
};

export function EstadoBadge({ estado }) {
  if (!estado) return null;
  const clase = ESTILOS_ESTADO[estado] || "bg-emerald-50 text-emerald-700 border-emerald-200";
  return <span className={`inline-block text-[11px] border rounded-sm px-1.5 py-0.5 first-letter:uppercase ${clase}`}>{estado}</span>;
}

/**
 * Botones Editar / Duplicar / Anular de una fila.
 * `bloqueo`: texto que explica por qué no se puede editar/anular (p. ej. enviada a la DIAN).
 */
export function AccionesDocumento({ doc, modulo, tipoDoc, onEditar, onDuplicar, onAnular, bloqueo }) {
  const { puede } = useAuth();
  const { abrir } = useVistaDocumento();
  const ver = tipoDoc ? (
    <button onClick={() => abrir(doc, tipoDoc)} className="text-xs text-slate-600 hover:underline">
      Ver / imprimir
    </button>
  ) : null;
  if (doc.estado === "anulado") {
    return (
      <div className="flex gap-3 whitespace-nowrap">
        {ver}
        {onDuplicar && puede(modulo, "crear") && (
          <button onClick={() => onDuplicar(doc)} className="text-xs text-geifem-blue hover:underline">
            Duplicar
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="flex gap-3 whitespace-nowrap">
      {ver}
      {onEditar && puede(modulo, "editar") && !bloqueo && (
        <button onClick={() => onEditar(doc)} className="text-xs text-geifem-blue hover:underline">
          Editar
        </button>
      )}
      {onDuplicar && puede(modulo, "crear") && (
        <button onClick={() => onDuplicar(doc)} className="text-xs text-geifem-blue hover:underline">
          Duplicar
        </button>
      )}
      {onAnular && puede(modulo, "inactivar") && !bloqueo && (
        <button onClick={() => onAnular(doc)} className="text-xs text-red-600 hover:underline">
          Anular
        </button>
      )}
      {bloqueo && <span className="text-[11px] text-slate-400" title={bloqueo}>bloqueado</span>}
    </div>
  );
}

/**
 * Diálogo de anulación. Un documento numerado no se borra: se anula, conserva
 * su número y se revierten sus efectos (asientos, inventario, saldos).
 */
export function useAnulacion(onListo) {
  const [doc, setDoc] = useState(null);
  const [endpoint, setEndpoint] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const pedir = (documento, url) => {
    setDoc(documento);
    setEndpoint(url);
    setMotivo("");
    setError(null);
  };

  const confirmar = async () => {
    setEnviando(true);
    setError(null);
    try {
      await api.post(endpoint, { motivo: motivo || null });
      setDoc(null);
      onListo?.();
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setEnviando(false);
    }
  };

  const modal = (
    <Modal
      open={Boolean(doc)}
      onClose={() => setDoc(null)}
      title={`Anular ${numeroDoc(doc)}`}
      footer={
        <>
          <button onClick={() => setDoc(null)} className="px-3 py-1.5 rounded-sm border border-slate-300 text-sm">
            Cancelar
          </button>
          <button
            onClick={confirmar}
            disabled={enviando}
            className="px-3 py-1.5 rounded-sm bg-red-600 text-white text-sm disabled:opacity-60"
          >
            {enviando ? "Anulando…" : "Anular documento"}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-600 mb-3">
        El documento conservará su número y quedará marcado como anulado. Se revierten sus asientos
        contables y, si aplica, sus movimientos de inventario y saldos de cartera.
      </p>
      <FormField label="Motivo (opcional)">
        <Input value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </FormField>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </Modal>
  );

  return { pedir, modal };
}

/** Encabezado del formulario según el modo (nuevo / editar / duplicar). */
export function tituloModo(modo, nombre, doc) {
  if (modo === "editar") return `Editar ${nombre} ${numeroDoc(doc)}`;
  if (modo === "duplicar") return `Nuevo ${nombre} (copia de ${numeroDoc(doc)})`;
  return `Nuevo ${nombre}`;
}

export function Avisos({ error, mensaje }) {
  return (
    <>
      {error && (
        <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm px-3 py-2">{error}</div>
      )}
      {mensaje && (
        <div className="mb-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded-sm px-3 py-2">
          {mensaje}
        </div>
      )}
    </>
  );
}

/** Selector de cuentas del PUC que reciben movimientos ("1105 — Caja"). */
export function SelectorCuenta({ cuentas, value, onChange, porCodigo = false, vacio = "Buscar cuenta por código o nombre…", ...rest }) {
  const opciones = useMemo(
    () =>
      cuentas
        .filter((c) => c.acepta_movimientos !== false && c.activo !== false)
        .sort((a, b) => a.codigo.localeCompare(b.codigo)),
    [cuentas]
  );
  const clave = (c) => (porCodigo ? c.codigo : c.id);
  const actual = opciones.find((c) => clave(c) === value);
  const etiqueta = actual ? `${actual.codigo} — ${actual.nombre}` : "";
  const [texto, setTexto] = useState(null); // null = muestra la selección
  const [abierto, setAbierto] = useState(false);

  const q = (texto ?? "").trim().toLowerCase();
  const visibles = (q ? opciones.filter((c) => `${c.codigo} ${c.nombre}`.toLowerCase().includes(q)) : opciones).slice(0, 50);

  const elegir = (c) => {
    onChange(c ? clave(c) : "");
    setTexto(null);
    setAbierto(false);
  };

  return (
    <div className="relative">
      <input
        {...rest}
        value={texto ?? etiqueta}
        placeholder={vacio}
        onFocus={(e) => { setAbierto(true); e.target.select(); }}
        onChange={(e) => { setTexto(e.target.value); setAbierto(true); }}
        onBlur={() => setTimeout(() => { setAbierto(false); setTexto(null); }, 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && abierto && visibles.length) { e.preventDefault(); elegir(visibles[0]); }
          if (e.key === "Escape") { setAbierto(false); setTexto(null); }
        }}
        className="w-full border border-slate-300 rounded-sm px-2 py-2 bg-white text-sm focus:ring-2 focus:ring-geifem-blue focus:outline-hidden"
      />
      {abierto && (
        <ul className="absolute z-30 mt-1 w-full max-h-56 overflow-auto bg-white border border-slate-300 rounded-sm shadow-lg text-sm">
          {value && <li onMouseDown={() => elegir(null)} className="px-2 py-1.5 text-slate-500 hover:bg-slate-100 cursor-pointer">Quitar selección</li>}
          {visibles.length === 0 && <li className="px-2 py-1.5 text-slate-500">Sin coincidencias</li>}
          {visibles.map((c) => (
            <li key={c.id} onMouseDown={() => elegir(c)} className="px-2 py-1.5 hover:bg-geifem-blue/10 cursor-pointer">
              <span className="font-mono text-xs text-slate-500 mr-2">{c.codigo}</span>{c.nombre}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
