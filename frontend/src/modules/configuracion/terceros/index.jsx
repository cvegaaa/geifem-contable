import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";

const TIPOS = [
  { valor: "cliente", etiqueta: "Cliente" },
  { valor: "proveedor", etiqueta: "Proveedor" },
  { valor: "ambos", etiqueta: "Cliente y proveedor" },
  { valor: "otro", etiqueta: "Otro" },
];
const PERSONAS = [
  { valor: "natural", etiqueta: "Persona natural" },
  { valor: "juridica", etiqueta: "Persona jurídica" },
];
const DOCUMENTOS = [
  { valor: "CC", etiqueta: "Cédula de ciudadanía" },
  { valor: "NIT", etiqueta: "NIT" },
  { valor: "CE", etiqueta: "Cédula de extranjería" },
  { valor: "PA", etiqueta: "Pasaporte" },
  { valor: "TI", etiqueta: "Tarjeta de identidad" },
];
const REGIMENES = [
  { valor: "ORDINARIO", etiqueta: "Ordinario" },
  { valor: "SIMPLE", etiqueta: "SIMPLE (no se le practica retención en la fuente)" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Terceros"
      descripcion="Clientes, proveedores y demás contactos. Su perfil tributario define qué retenciones se aplican en cada documento."
      endpoint="/api/configuracion/terceros"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "tipo", label: "Tipo", render: (r) => etiquetaDe(TIPOS, r.tipo) },
        { key: "tipo_documento", label: "Documento", render: (r) => `${r.tipo_documento || ""} ${r.numero_documento || ""}` },
        { key: "regimen", label: "Régimen", render: (r) => (r.regimen === "SIMPLE" ? "SIMPLE" : "Ordinario") },
        { key: "telefono", label: "Teléfono" },
        { key: "email", label: "Email" },
      ]}
      fields={[
        { key: "nombre", label: "Nombre o razón social", required: true },
        { key: "tipo", label: "Tipo", type: "select", options: TIPOS, required: true, defecto: "cliente" },
        { key: "tipo_persona", label: "Persona", type: "select", options: PERSONAS, defecto: "natural" },
        { key: "tipo_documento", label: "Tipo de documento", type: "select", options: DOCUMENTOS, defecto: "CC" },
        { key: "numero_documento", label: "Número de documento", required: true },
        { key: "dv", label: "DV (solo NIT)" },
        { key: "direccion", label: "Dirección" },
        { key: "ciudad", label: "Ciudad" },
        { key: "email", label: "Email", type: "email" },
        { key: "telefono", label: "Teléfono" },
        {
          seccion: "Perfil tributario",
          hint: "Determina las retenciones: a tus proveedores (las practicas tú) y de tus clientes (te las practican).",
        },
        { key: "regimen", label: "Régimen del tercero", type: "select", options: REGIMENES, defecto: "ORDINARIO" },
        { key: "responsable_iva", label: "Responsable de IVA", type: "checkbox", defecto: true, textoCheckbox: "Sí (si no, no se le retiene IVA)" },
        { key: "declarante_renta", label: "Declarante de renta", type: "checkbox", defecto: true, textoCheckbox: "Sí (los no declarantes tienen tarifas más altas en algunos conceptos)" },
        { key: "autorretenedor", label: "Autorretenedor", type: "checkbox", defecto: false, textoCheckbox: "Sí (no se le practica retención en la fuente)" },
        { key: "agente_retenedor", label: "Agente retenedor", type: "checkbox", defecto: false, textoCheckbox: "Sí, me practica retención en la fuente y de ICA al pagarme" },
        { key: "agente_reteiva", label: "Agente de ReteIVA", type: "checkbox", defecto: false, textoCheckbox: "Sí, me practica retención de IVA al pagarme" },
        { key: "gran_contribuyente", label: "Gran contribuyente", type: "checkbox", defecto: false, textoCheckbox: "Sí (actúa como agente retenedor)" },
      ]}
    />
  );
}
