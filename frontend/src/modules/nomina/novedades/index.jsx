import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";
import { fmtCOP } from "../../../shared/documentos/index.jsx";

export const TIPOS_NOVEDAD = [
  { valor: "hora_extra_diurna", etiqueta: "Hora extra diurna (horas)" },
  { valor: "hora_extra_nocturna", etiqueta: "Hora extra nocturna (horas)" },
  { valor: "recargo_nocturno", etiqueta: "Recargo nocturno (horas)" },
  { valor: "recargo_dominical_festivo", etiqueta: "Recargo dominical o festivo (horas)" },
  { valor: "hora_extra_diurna_dominical", etiqueta: "Hora extra diurna dominical/festiva (horas)" },
  { valor: "hora_extra_nocturna_dominical", etiqueta: "Hora extra nocturna dominical/festiva (horas)" },
  { valor: "recargo_nocturno_dominical", etiqueta: "Recargo nocturno dominical/festivo (horas)" },
  { valor: "incapacidad_general", etiqueta: "Incapacidad por enfermedad general (días)" },
  { valor: "incapacidad_laboral", etiqueta: "Incapacidad laboral, ARL (días)" },
  { valor: "licencia_maternidad_paternidad", etiqueta: "Licencia de maternidad o paternidad (días)" },
  { valor: "licencia_remunerada", etiqueta: "Licencia remunerada (días)" },
  { valor: "vacaciones", etiqueta: "Vacaciones disfrutadas (días)" },
  { valor: "licencia_no_remunerada", etiqueta: "Licencia no remunerada (días, descuenta)" },
  { valor: "suspension", etiqueta: "Suspensión (días, descuenta)" },
  { valor: "comision", etiqueta: "Comisión (valor, salarial)" },
  { valor: "bonificacion_salarial", etiqueta: "Bonificación salarial (valor)" },
  { valor: "bonificacion_no_salarial", etiqueta: "Bonificación no salarial (valor)" },
  { valor: "otro_devengo_no_salarial", etiqueta: "Otro devengo no salarial (valor)" },
  { valor: "prestamo", etiqueta: "Descuento por préstamo (valor)" },
  { valor: "embargo", etiqueta: "Embargo (valor)" },
  { valor: "libranza", etiqueta: "Libranza (valor)" },
  { valor: "otra_deduccion", etiqueta: "Otra deducción (valor)" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Novedades de nómina"
      descripcion="Registra lo que afecta la liquidación del periodo en el que cae la fecha: horas, incapacidades, licencias, vacaciones, comisiones y descuentos. Después de agregar o corregir novedades, recalcula el periodo desde Liquidación de nómina."
      endpoint="/api/nomina/novedades"
      modulo="nomina"
      columns={[
        { key: "fecha_inicio", label: "Fecha" },
        { key: "empleado_nombre", label: "Empleado" },
        { key: "tipo", label: "Novedad", render: (r) => etiquetaDe(TIPOS_NOVEDAD, r.tipo) },
        { key: "cantidad", label: "Cantidad", render: (r) => r.cantidad ?? "—" },
        { key: "valor", label: "Valor", render: (r) => (r.valor ? fmtCOP(r.valor) : "—") },
        { key: "descripcion", label: "Detalle" },
      ]}
      fields={[
        {
          key: "empleado_id", label: "Empleado", type: "ref", endpoint: "/api/nomina/empleados", required: true,
          etiqueta: (e) => [e.primer_nombre, e.primer_apellido].filter(Boolean).join(" ") + ` (${e.numero_documento})`,
        },
        { key: "tipo", label: "Tipo de novedad", type: "select", options: TIPOS_NOVEDAD, required: true },
        { key: "fecha_inicio", label: "Fecha", type: "date", required: true, hint: "Define el periodo en el que se liquida." },
        { key: "cantidad", label: "Cantidad (horas o días)", type: "number", hint: "Para horas, incapacidades, licencias y vacaciones." },
        { key: "valor", label: "Valor en pesos", type: "number", hint: "Para comisiones, bonificaciones y descuentos." },
        { key: "dias_previos", label: "Días previos de la misma incapacidad", type: "number",
          hint: "Solo incapacidad general: si continúa de un periodo anterior, cuántos días ya se habían contado (los 2 primeros paga el empleador)." },
        { key: "descripcion", label: "Detalle" },
      ]}
    />
  );
}
