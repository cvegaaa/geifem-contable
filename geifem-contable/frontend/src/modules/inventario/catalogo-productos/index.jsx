import ResourceCrud from "../../_ResourceCrud.jsx";
export default function Page() {
  return (
    <ResourceCrud
      titulo="Catálogo de productos"
      endpoint="/api/inventario/catalogo-productos"
      modulo="inventario"
      columns={[
        { key: "sku", label: "SKU" },
        { key: "nombre", label: "Nombre" },
        { key: "categoria", label: "Categoría" },
        { key: "existencia", label: "Existencia" },
        { key: "costo_promedio_ponderado", label: "Costo PP" },
      ]}
      fields={[
        { key: "sku", label: "SKU" },
        { key: "nombre", label: "Nombre" },
        { key: "categoria", label: "Categoría" },
        { key: "unidad_medida_id", label: "Unidad de medida (id)" },
        { key: "costo_promedio_ponderado", label: "Costo inicial", type: "number" },
        { key: "existencia", label: "Existencia inicial", type: "number" },
      ]}
    />
  );
}
