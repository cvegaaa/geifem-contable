import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Tipos de documento"
      descripcion="Prefijos de referencia para documentos internos. La numeración de cada documento es automática."
      endpoint="/api/configuracion/tipos-documento"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "prefijo", label: "Prefijo" },
      ]}
      fields={[
        { key: "nombre", label: "Nombre", required: true },
        { key: "prefijo", label: "Prefijo", required: true },
      ]}
    />
  );
}
