import { useMemo, useState } from "react";

/**
 * Lista desplegable con búsqueda: se escribe parte del código o del nombre y se elige una opción.
 * `opciones`: [{ valor, etiqueta }]. `onChange(valor)`; "" = sin selección.
 */
export default function SelectorLista({ opciones, value, onChange, placeholder = "Buscar…", disabled = false }) {
  const actual = opciones.find((o) => o.valor === value);
  const etiqueta = actual ? actual.etiqueta : value || "";
  const [texto, setTexto] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const q = (texto ?? "").trim().toLowerCase();
  const visibles = useMemo(
    () => (q ? opciones.filter((o) => o.etiqueta.toLowerCase().includes(q)) : opciones).slice(0, 60),
    [opciones, q]
  );
  const elegir = (o) => { onChange(o ? o.valor : ""); setTexto(null); setAbierto(false); };
  return (
    <div className="relative">
      <input
        value={texto ?? etiqueta} disabled={disabled} placeholder={placeholder}
        onFocus={(e) => { setAbierto(true); e.target.select(); }}
        onChange={(e) => { setTexto(e.target.value); setAbierto(true); }}
        onBlur={() => setTimeout(() => { setAbierto(false); setTexto(null); }, 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && abierto && visibles.length) { e.preventDefault(); elegir(visibles[0]); }
          if (e.key === "Escape") { setAbierto(false); setTexto(null); }
        }}
        className="w-full border border-slate-300 rounded-sm px-2 py-2 bg-white text-sm focus:ring-2 focus:ring-geifem-blue focus:outline-hidden disabled:bg-slate-100"
      />
      {abierto && (
        <ul className="absolute z-30 mt-1 w-full max-h-60 overflow-auto bg-white border border-slate-300 rounded-sm shadow-lg text-sm">
          {value && <li onMouseDown={() => elegir(null)} className="px-2 py-1.5 text-slate-500 hover:bg-slate-100 cursor-pointer">Quitar selección</li>}
          {visibles.length === 0 && <li className="px-2 py-1.5 text-slate-500">Sin coincidencias</li>}
          {visibles.map((o) => (
            <li key={o.valor} onMouseDown={() => elegir(o)} className="px-2 py-1.5 hover:bg-geifem-blue/10 cursor-pointer">{o.etiqueta}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
