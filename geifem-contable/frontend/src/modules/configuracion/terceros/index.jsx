import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Terceros"
      endpoint="/api/configuracion/terceros"
      modulo="configuracion"
      columns={[{key:"nombre",label:"Nombre"},{key:"tipo",label:"Tipo"},{key:"tipo_documento",label:"T. Doc"},{key:"numero_documento",label:"Documento"}]}
      fields={[{key:"nombre",label:"Nombre"},{key:"tipo",label:"Tipo (cliente|proveedor|otro)"},{key:"tipo_persona",label:"Persona (natural|juridica)"},{key:"tipo_documento",label:"Tipo documento (CC|NIT|CE|pasaporte)"},{key:"numero_documento",label:"Número documento"},{key:"email",label:"Email"},{key:"telefono",label:"Teléfono"}]}
    />
  );
}
