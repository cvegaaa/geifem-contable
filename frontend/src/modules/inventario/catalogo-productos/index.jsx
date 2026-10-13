import ResourceCrud from "../../_ResourceCrud.jsx";
import { fmtCOP } from "../../../shared/documentos/index.jsx";

const TIPOS_IVA = [
  { valor: "gravado", etiqueta: "Gravado" },
  { valor: "excluido", etiqueta: "Excluido (no causa IVA)" },
  { valor: "exento", etiqueta: "Exento (tarifa 0%, con derecho a devolución)" },
];
const TARIFAS_IVA = [
  { valor: "19", etiqueta: "19%" },
  { valor: "5", etiqueta: "5%" },
];

const hintImpuestos = (perfil) => {
  if (!perfil) return "";
  const notas = perfil.notas?.length ? perfil.notas.join(" ") : "";
  return `Las opciones disponibles dependen del perfil tributario de tu empresa. ${notas}`;
};

export default function Page() {
  return (
    <ResourceCrud
      titulo="Productos y servicios"
      descripcion="Las existencias y el costo promedio los calcula el kardex con tus compras, ventas y ajustes."
      endpoint="/api/inventario/catalogo-productos"
      modulo="inventario"
      columns={[
        { key: "sku", label: "Código" },
        { key: "nombre", label: "Nombre" },
        { key: "categoria", label: "Categoría" },
        { key: "precio_venta", label: "Precio de venta", render: (r) => fmtCOP(r.precio_venta) },
        { key: "iva", label: "IVA", render: (r) => (r.tipo_iva && r.tipo_iva !== "gravado" ? r.tipo_iva : `${Number(r.tarifa_iva ?? 19)}%`) },
        { key: "costo_promedio_ponderado", label: "Costo promedio", render: (r) => fmtCOP(r.costo_promedio_ponderado || 0) },
        { key: "inventariable", label: "Inventario", render: (r) => (r.inventariable === false ? "Servicio" : "Sí") },
      ]}
      fields={[
        { key: "sku", label: "Código (SKU)", required: true },
        { key: "nombre", label: "Nombre", required: true },
        { key: "categoria", label: "Categoría" },
        {
          key: "unidad_medida_id",
          label: "Unidad de medida",
          type: "ref",
          endpoint: "/api/configuracion/unidades-medida",
          etiqueta: (u) => `${u.nombre} (${u.abreviatura})`,
        },
        { key: "precio_venta", label: "Precio de venta", type: "number" },
        {
          key: "inventariable",
          label: "Controla inventario",
          type: "checkbox",
          defecto: true,
          textoCheckbox: "Sí (desmárcalo para servicios)",
        },

        { seccion: "Impuestos", hint: hintImpuestos },
        { key: "tipo_iva", label: "Tipo de IVA", type: "select", options: TIPOS_IVA, defecto: "gravado", mostrar: (p) => p.cobra_iva },
        { key: "tarifa_iva", label: "Tarifa de IVA", type: "select", options: TARIFAS_IVA, defecto: "19", mostrar: (p) => p.cobra_iva },
        {
          key: "concepto_retefuente_venta_id",
          label: "Retención en la fuente que te practican al venderlo",
          type: "ref",
          endpoint: "/api/configuracion/conceptos-retencion",
          etiqueta: (c) => `${c.nombre} (${c.tarifa}%)`,
          vacio: "Ninguna",
          mostrar: (p) => p.sufre_retefuente,
        },
        {
          key: "concepto_retefuente_compra_id",
          label: "Retención en la fuente que practicas al comprarlo",
          type: "ref",
          endpoint: "/api/configuracion/conceptos-retencion",
          etiqueta: (c) => `${c.nombre} (${c.tarifa}%)`,
          vacio: "Ninguna",
          mostrar: (p) => p.practica_retefuente,
        },
        {
          key: "impuesto_consumo_id",
          label: "Impuesto al consumo (INC)",
          type: "ref",
          endpoint: "/api/configuracion/impuestos",
          etiqueta: (i) => `${i.nombre} (${i.tarifa}%)`,
          vacio: "No genera impuesto al consumo",
        },
        {
          key: "aplica_reteica",
          label: "ReteICA",
          type: "checkbox",
          defecto: true,
          textoCheckbox: "Aplica ReteICA (ventas y compras de este producto)",
          mostrar: (p) => p.sufre_reteica || p.practica_reteica,
        },

        {
          seccion: "Cuentas contables (opcional)",
          hint: "Déjalas vacías para usar las de Configuración › Parámetros contables.",
        },
        { key: "cuenta_ingreso", label: "Cuenta de ingreso por venta", type: "cuenta", prefijos: ["4"], vacio: "Usar la de la empresa" },
        { key: "cuenta_inventario", label: "Cuenta de inventario", type: "cuenta", prefijos: ["14"], vacio: "Usar la de la empresa" },
        { key: "cuenta_costo", label: "Cuenta de costo de venta", type: "cuenta", prefijos: ["6", "7"], vacio: "Usar la de la empresa" },
      ]}
    />
  );
}
