import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Resoluciones DIAN"
      endpoint="/api/configuracion/resoluciones-dian"
      modulo="configuracion"
      columns={[{key:"numero_resolucion",label:"Resolución"},{key:"prefijo",label:"Prefijo"},{key:"rango_desde",label:"Desde"},{key:"rango_hasta",label:"Hasta"},{key:"fecha_fin",label:"Vence"}]}
      fields={[{key:"numero_resolucion",label:"Número resolución"},{key:"prefijo",label:"Prefijo"},{key:"tipo_documento_id",label:"Tipo documento (id)"},{key:"rango_desde",label:"Rango desde",type:"number"},{key:"rango_hasta",label:"Rango hasta",type:"number"},{key:"fecha_inicio",label:"Fecha inicio",type:"date"},{key:"fecha_fin",label:"Fecha fin",type:"date"}]}
    />
  );
}
