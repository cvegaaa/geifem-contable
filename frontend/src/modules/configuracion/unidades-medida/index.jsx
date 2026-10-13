import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Unidades de medida"
      endpoint="/api/configuracion/unidades-medida"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "abreviatura", label: "Abreviatura" },
      ]}
      fields={[
        { key: "nombre", label: "Nombre", required: true, hint: "Ej.: Unidad, Kilogramo, Caja x 12" },
        { key: "abreviatura", label: "Abreviatura", required: true },
      ]}
    />
  );
}
