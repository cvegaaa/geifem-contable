import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Centros de costo"
      endpoint="/api/configuracion/centros-costo"
      modulo="configuracion"
      columns={[{key:"codigo",label:"Código"},{key:"nombre",label:"Nombre"}]}
      fields={[{key:"codigo",label:"Código"},{key:"nombre",label:"Nombre"}]}
    />
  );
}
