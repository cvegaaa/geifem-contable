import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Unidades de medida"
      endpoint="/api/configuracion/unidades-medida"
      modulo="configuracion"
      columns={[{key:"nombre",label:"Nombre"},{key:"abreviatura",label:"Abrev."}]}
      fields={[{key:"nombre",label:"Nombre"},{key:"abreviatura",label:"Abreviatura"}]}
    />
  );
}
