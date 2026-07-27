import { useState } from "react";

const HOY = () => new Date().toISOString().slice(0, 10);

function inicioMes() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function inicioTrimestre() {
  const d = new Date();
  const q = Math.floor(d.getMonth() / 3) * 3;
  return new Date(d.getFullYear(), q, 1).toISOString().slice(0, 10);
}
function inicioAno() {
  return new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
}

const PRESETS = [
  { key: "mes", label: "Mes actual", desde: inicioMes, hasta: HOY },
  { key: "trimestre", label: "Trimestre actual", desde: inicioTrimestre, hasta: HOY },
  { key: "ano", label: "Año fiscal actual", desde: inicioAno, hasta: HOY },
  { key: "personalizado", label: "Personalizado" },
];

/**
 * Componente compartido de selección de rango de fechas.
 * Uso: <SelectorRangoFechas value={{desde, hasta}} onChange={fn} />
 */
export default function SelectorRangoFechas({ value, onChange }) {
  const [preset, setPreset] = useState("mes");

  const aplicarPreset = (key) => {
    setPreset(key);
    const p = PRESETS.find((x) => x.key === key);
    if (p && p.desde && p.hasta) {
      onChange({ desde: p.desde(), hasta: p.hasta() });
    }
  };

  return (
    <div className="flex flex-wrap items-end gap-3 bg-white border border-slate-200 rounded-lg p-3">
      <div>
        <label className="block text-xs uppercase text-slate-500 mb-1">Preset</label>
        <select
          className="border border-slate-300 rounded px-2 py-1 text-sm"
          value={preset}
          onChange={(e) => aplicarPreset(e.target.value)}
        >
          {PRESETS.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs uppercase text-slate-500 mb-1">Desde</label>
        <input
          type="date"
          className="border border-slate-300 rounded px-2 py-1 text-sm"
          value={value?.desde || ""}
          onChange={(e) => {
            setPreset("personalizado");
            onChange({ ...value, desde: e.target.value });
          }}
        />
      </div>
      <div>
        <label className="block text-xs uppercase text-slate-500 mb-1">Hasta</label>
        <input
          type="date"
          className="border border-slate-300 rounded px-2 py-1 text-sm"
          value={value?.hasta || ""}
          onChange={(e) => {
            setPreset("personalizado");
            onChange({ ...value, hasta: e.target.value });
          }}
        />
      </div>
    </div>
  );
}
