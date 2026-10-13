import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Bodegas"
      endpoint="/api/inventario/bodegas"
      modulo="inventario"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "direccion", label: "Dirección" },
        {
          key: "activo",
          label: "Estado",
          render: (r) => (r.activo === false ? "Inactiva" : "Activa"),
        },
      ]}
      fields={[
        { key: "nombre", label: "Nombre" },
        { key: "direccion", label: "Dirección" },
      ]}
    />
  );
}
