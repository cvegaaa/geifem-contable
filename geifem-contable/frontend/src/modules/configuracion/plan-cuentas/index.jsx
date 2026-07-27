import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Plan de cuentas"
      endpoint="/api/configuracion/plan-cuentas"
      modulo="configuracion"
      columns={[{key:"codigo",label:"Código"},{key:"nombre",label:"Nombre"},{key:"naturaleza",label:"Naturaleza"},{key:"nivel",label:"Nivel"}]}
      fields={[{key:"codigo",label:"Código"},{key:"nombre",label:"Nombre"},{key:"naturaleza",label:"Naturaleza (debito|credito)"},{key:"nivel",label:"Nivel",type:"number"},{key:"cuenta_padre_id",label:"Cuenta padre (id, opcional)"}]}
    />
  );
}
