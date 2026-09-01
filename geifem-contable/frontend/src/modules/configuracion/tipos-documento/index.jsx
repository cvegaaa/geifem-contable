import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Tipos de documento"
      endpoint="/api/configuracion/tipos-documento"
      modulo="configuracion"
      columns={[{key:"nombre",label:"Nombre"},{key:"prefijo",label:"Prefijo"},{key:"consecutivo_actual",label:"Consecutivo"}]}
      fields={[{key:"nombre",label:"Nombre"},{key:"prefijo",label:"Prefijo"},{key:"consecutivo_actual",label:"Consecutivo actual",type:"number"}]}
    />
  );
}
