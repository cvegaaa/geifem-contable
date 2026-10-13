import api from "../../../core/api.js";
import { mensajeError } from "../../../shared/documentos/index.jsx";
import ResourceCrud from "../../_ResourceCrud.jsx";

const TIPOS = [
  { valor: "01", etiqueta: "Factura electrónica de venta" },
  { valor: "02", etiqueta: "Factura de exportación" },
  { valor: "03", etiqueta: "Factura por contingencia" },
  { valor: "07", etiqueta: "Documento equivalente POS" },
  { valor: "05", etiqueta: "Documento soporte" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Resoluciones DIAN"
      descripcion="Rangos de numeración autorizados. Cada factura toma su número de aquí automáticamente. Cuando se conecte el proveedor tecnológico, «Sincronizar con la DIAN» trae y mantiene estas resoluciones desde el portal; mientras tanto se registran a mano."
      endpoint="/api/configuracion/resoluciones-dian"
      modulo="configuracion"
      extra={({ recargar, avisar }) => (
        <button
          onClick={async () => {
            try {
              const { data } = await api.post("/api/configuracion/resoluciones-dian/sincronizar");
              avisar(`Sincronizado con la DIAN: ${data.creadas} nuevas y ${data.actualizadas} actualizadas`);
              recargar();
            } catch (err) {
              avisar(mensajeError(err));
            }
          }}
          className="border border-geifem-navy text-geifem-navy text-sm px-3 py-2 rounded-sm"
          title="Consulta las resoluciones habilitadas en el portal de la DIAN"
        >
          Sincronizar con la DIAN
        </button>
      )}
      columns={[
        { key: "numero_resolucion", label: "Resolución" },
        { key: "tipo_documento", label: "Documento", render: (r) => TIPOS.find((t) => t.valor === r.tipo_documento)?.etiqueta || "Factura electrónica de venta" },
        { key: "prefijo", label: "Prefijo" },
        { key: "rango", label: "Rango", render: (r) => `${r.rango_desde ?? ""} – ${r.rango_hasta ?? ""}` },
        { key: "consecutivo_actual", label: "Último usado", render: (r) => r.consecutivo_actual ?? "—" },
        { key: "vigencia", label: "Vigencia", render: (r) => `${r.fecha_inicio || ""} a ${r.fecha_fin || ""}` },
        { key: "origen", label: "Origen", render: (r) => (r.origen === "dian" ? "DIAN" : "Manual") },
      ]}
      fields={[
        { key: "tipo_documento", label: "Tipo de documento", type: "select", options: TIPOS, defecto: "01" },
        { key: "numero_resolucion", label: "Número de resolución", required: true },
        { key: "fecha_resolucion", label: "Fecha de la resolución", type: "date" },
        { key: "prefijo", label: "Prefijo", required: true, hint: "Ej.: FE, SETP" },
        { key: "rango_desde", label: "Rango desde", type: "number", required: true },
        { key: "rango_hasta", label: "Rango hasta", type: "number", required: true },
        { key: "fecha_inicio", label: "Vigente desde", type: "date", required: true },
        { key: "fecha_fin", label: "Vigente hasta", type: "date", required: true },
        { key: "clave_tecnica", label: "Clave técnica", hint: "La entrega la DIAN con la resolución de facturación; se usa para calcular el CUFE." },
      ]}
    />
  );
}
