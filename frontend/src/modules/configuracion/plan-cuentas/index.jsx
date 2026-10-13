import api from "../../../core/api.js";
import { mensajeError } from "../../../shared/documentos/index.jsx";
import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";

const NATURALEZAS = [
  { valor: "debito", etiqueta: "Débito" },
  { valor: "credito", etiqueta: "Crédito" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Plan de cuentas"
      descripcion="Cuentas del PUC de la empresa. Las de 4 o más dígitos reciben movimientos; las de 1 y 2 dígitos solo agrupan."
      endpoint="/api/configuracion/plan-cuentas"
      modulo="configuracion"
      extra={({ recargar, avisar }) => (
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
      )}
      columns={[
        { key: "codigo", label: "Código", render: (r) => <span className={r.acepta_movimientos === false ? "font-semibold" : ""}>{r.codigo}</span> },
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
