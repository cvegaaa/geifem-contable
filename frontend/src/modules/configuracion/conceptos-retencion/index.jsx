import api from "../../../core/api.js";
import { mensajeError } from "../../../shared/documentos/index.jsx";
import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";

const TIPOS = [
  { valor: "retefuente", etiqueta: "Retención en la fuente (renta)" },
  { valor: "reteica", etiqueta: "ReteICA (por mil)" },
  { valor: "reteiva", etiqueta: "ReteIVA (% del IVA)" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Conceptos de retención"
      descripcion="Tarifas y bases mínimas (en UVT) de cada retención. Se asignan a productos, líneas de compra y facturas de proveedor. Los conceptos sugeridos son un punto de partida: valídalos con tu contador y ajusta el ReteICA a tu municipio."
      endpoint="/api/configuracion/conceptos-retencion"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Concepto" },
        { key: "tipo", label: "Tipo", render: (r) => etiquetaDe(TIPOS, r.tipo) },
        { key: "tarifa", label: "Tarifa", render: (r) => (r.tipo === "reteica" ? `${r.tarifa} ‰` : `${r.tarifa} %`) },
        { key: "tarifa_no_declarante", label: "No declarante", render: (r) => (r.tarifa_no_declarante ? `${r.tarifa_no_declarante} %` : "—") },
        { key: "base_uvt", label: "Base mínima", render: (r) => `${r.base_uvt || 0} UVT` },
      ]}
      fields={[
        { key: "tipo", label: "Tipo", type: "select", options: TIPOS, required: true, defecto: "retefuente" },
        { key: "nombre", label: "Nombre del concepto", required: true },
        { key: "tarifa", label: "Tarifa", type: "number", required: true, hint: "% para ReteFuente y ReteIVA; por mil para ReteICA" },
        { key: "tarifa_no_declarante", label: "Tarifa a no declarantes (opcional)", type: "number" },
        { key: "base_uvt", label: "Base mínima en UVT", type: "number", hint: "No se retiene si la base es menor (UVT 2026: $52.374)" },
        { seccion: "Cuentas contables (opcional)", hint: "Vacías usan las de Parámetros contables. Útil para subcuentas por concepto (p. ej. 236540 compras, 236525 servicios)." },
        { key: "cuenta_pasivo", label: "Cuenta de la retención que tú practicas (pasivo)", type: "cuenta", prefijos: ["23"], vacio: "Usar la de Parámetros contables" },
        { key: "cuenta_favor", label: "Cuenta de la retención que te practican (a favor)", type: "cuenta", prefijos: ["13"], vacio: "Usar la de Parámetros contables" },
      ]}
      extra={({ recargar, avisar }) => (
        <button
          onClick={async () => {
            try {
              const { data } = await api.post("/api/configuracion/conceptos-retencion/cargar-sugeridos");
              avisar(data.agregados ? `${data.agregados} conceptos sugeridos agregados` : "Ya tienes todos los conceptos sugeridos");
              recargar();
            } catch (err) {
              avisar(mensajeError(err));
            }
          }}
          className="border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm"
        >
          Cargar conceptos sugeridos
        </button>
      )}
    />
  );
}
