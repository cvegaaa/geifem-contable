import { useState } from "react";
import api from "../../../core/api.js";
import { mensajeError } from "../../../shared/documentos/index.jsx";
import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";

const NATURALEZAS = [
  { valor: "debito", etiqueta: "Débito" },
  { valor: "credito", etiqueta: "Crédito" },
];

const NIVELES = [
  { digitos: 1, etiqueta: "Clases (1 dígito)" },
  { digitos: 2, etiqueta: "Grupos (2 dígitos)" },
  { digitos: 4, etiqueta: "Cuentas (4 dígitos)" },
  { digitos: 6, etiqueta: "Subcuentas auxiliares (6 dígitos)" },
  { digitos: 12, etiqueta: "Todo el detalle" },
];

export default function Page() {
  // Por defecto se abre hasta el nivel de detalle de 6 dígitos.
  const [nivel, setNivel] = useState(6);
  return (
    <ResourceCrud
      titulo="Plan de cuentas"
      filtrar={(r) => String(r.codigo).length <= nivel}
      ordenar={(a, b) => String(a.codigo).localeCompare(String(b.codigo), "es", { numeric: true })}
      descripcion="Cuentas del PUC de la empresa, abiertas hasta el detalle de 6 dígitos (subcuentas auxiliares). Las de 1 y 2 dígitos solo agrupan; las de 4 y 6 dígitos reciben movimientos: usa de preferencia las de 6 para el detalle."
      endpoint="/api/configuracion/plan-cuentas"
      modulo="configuracion"
      extra={({ recargar, avisar }) => (
        <>
        <select value={nivel} onChange={(e) => setNivel(Number(e.target.value))}
          className="border border-slate-300 rounded-sm px-2 py-2 text-sm bg-white" title="Nivel de detalle">
          {NIVELES.map((n) => <option key={n.digitos} value={n.digitos}>{n.etiqueta}</option>)}
        </select>
        <button
          onClick={async () => {
            try {
              const { data } = await api.post("/api/configuracion/plan-cuentas/cargar-sugeridas");
              avisar(data.agregadas ? `Se agregaron ${data.agregadas} cuentas: ${data.codigos.join(", ")}` : "Tu plan ya tiene todas las cuentas sugeridas");
              recargar();
            } catch (err) {
              avisar(mensajeError(err));
            }
          }}
          className="border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm"
          title="Agrega las cuentas base que falten (p. ej. impuesto al consumo y prestaciones sociales) sin tocar las que ya tienes"
        >
          Completar con cuentas sugeridas
        </button>
        </>
      )}
      columns={[
        { key: "codigo", label: "Código", render: (r) => <span style={{ paddingLeft: `${(String(r.codigo).length / 2) * 6}px` }} className={r.acepta_movimientos === false ? "font-semibold" : ""}>{r.codigo}</span> },
        { key: "nombre", label: "Nombre", render: (r) => <span className={r.acepta_movimientos === false ? "font-semibold" : ""}>{r.nombre}</span> },
        { key: "naturaleza", label: "Naturaleza", render: (r) => etiquetaDe(NATURALEZAS, r.naturaleza) },
        { key: "acepta_movimientos", label: "Movimientos", render: (r) => (r.acepta_movimientos === false ? "Agrupa" : "Sí") },
      ]}
      fields={[
        { key: "codigo", label: "Código", required: true, hint: "Ej.: 110505 (subcuenta de 1105 Caja)" },
        { key: "nombre", label: "Nombre", required: true },
        { key: "naturaleza", label: "Naturaleza", type: "select", options: NATURALEZAS, required: true, defecto: "debito" },
        { key: "acepta_movimientos", label: "Recibe movimientos", type: "checkbox", defecto: true, textoCheckbox: "Sí, se puede usar en comprobantes" },
      ]}
    />
  );
}
