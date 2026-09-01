import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Formas de pago"
      endpoint="/api/configuracion/formas-pago"
      modulo="configuracion"
      columns={[{key:"nombre",label:"Nombre"},{key:"tipo",label:"Tipo"}]}
      fields={[{key:"nombre",label:"Nombre"},{key:"tipo",label:"Tipo (efectivo|transferencia|tarjeta|nequi|daviplata)"}]}
    />
  );
}
