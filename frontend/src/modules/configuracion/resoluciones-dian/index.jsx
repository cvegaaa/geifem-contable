import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Resoluciones DIAN"
      descripcion="Rangos de numeración autorizados. Cada factura toma su número de aquí automáticamente."
      endpoint="/api/configuracion/resoluciones-dian"
      modulo="configuracion"
      columns={[
        { key: "numero_resolucion", label: "Resolución" },
        { key: "prefijo", label: "Prefijo" },
        { key: "rango", label: "Rango", render: (r) => `${r.rango_desde ?? ""} – ${r.rango_hasta ?? ""}` },
        { key: "consecutivo_actual", label: "Último usado", render: (r) => r.consecutivo_actual ?? "—" },
        { key: "vigencia", label: "Vigencia", render: (r) => `${r.fecha_inicio || ""} a ${r.fecha_fin || ""}` },
      ]}
      fields={[
        { key: "numero_resolucion", label: "Número de resolución", required: true },
        { key: "prefijo", label: "Prefijo", required: true, hint: "Ej.: FE, SETP" },
        { key: "rango_desde", label: "Rango desde", type: "number", required: true },
        { key: "rango_hasta", label: "Rango hasta", type: "number", required: true },
        { key: "fecha_inicio", label: "Vigente desde", type: "date", required: true },
        { key: "fecha_fin", label: "Vigente hasta", type: "date", required: true },
      ]}
    />
  );
}
