import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Impuestos"
      endpoint="/api/configuracion/impuestos"
      modulo="configuracion"
      columns={[{key:"tipo",label:"Tipo"},{key:"tarifa",label:"Tarifa %"},{key:"base_minima",label:"Base mínima"},{key:"ciudad",label:"Ciudad"}]}
      fields={[{key:"tipo",label:"Tipo (IVA|INC|ICA|retencion)"},{key:"tarifa",label:"Tarifa (%)",type:"number"},{key:"base_minima",label:"Base mínima",type:"number"},{key:"ciudad",label:"Ciudad (si aplica ICA)"}]}
    />
  );
}
