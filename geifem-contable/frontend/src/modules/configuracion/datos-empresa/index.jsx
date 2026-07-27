import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Datos de empresa"
      endpoint="/api/configuracion/datos-empresa"
      modulo="configuracion"
      columns={[{key:"nit",label:"NIT"},{key:"razon_social",label:"Razón social"},{key:"regimen_tributario",label:"Régimen"},{key:"ciudad",label:"Ciudad"}]}
      fields={[{key:"nit",label:"NIT"},{key:"razon_social",label:"Razón social"},{key:"regimen_tributario",label:"Régimen (SIMPLE|COMUN)"},{key:"ciudad",label:"Ciudad"},{key:"actividad_ciiu",label:"Actividad CIIU"},{key:"logo_url",label:"Logo URL"}]}
    />
  );
}
