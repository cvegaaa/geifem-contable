import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";
import { fmtCOP } from "../../../shared/documentos/index.jsx";

const DOCUMENTOS = [
  { valor: "CC", etiqueta: "Cédula de ciudadanía" },
  { valor: "CE", etiqueta: "Cédula de extranjería" },
  { valor: "PA", etiqueta: "Pasaporte" },
  { valor: "PEP", etiqueta: "Permiso especial (PEP)" },
  { valor: "TI", etiqueta: "Tarjeta de identidad" },
];
const CONTRATOS = [
  { valor: "indefinido", etiqueta: "Término indefinido" },
  { valor: "fijo", etiqueta: "Término fijo" },
  { valor: "obra_labor", etiqueta: "Obra o labor" },
  { valor: "aprendizaje", etiqueta: "Aprendizaje (SENA)" },
  { valor: "practicas", etiqueta: "Prácticas" },
];
const FRECUENCIAS = [
  { valor: "mensual", etiqueta: "Mensual" },
  { valor: "quincenal", etiqueta: "Quincenal" },
];
const RIESGOS = ["I", "II", "III", "IV", "V"].map((r) => ({ valor: r, etiqueta: `Riesgo ${r}` }));
const CUENTAS = [
  { valor: "ahorros", etiqueta: "Ahorros" },
  { valor: "corriente", etiqueta: "Corriente" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Empleados"
      descripcion="Cada empleado se paga mensual o quincenal según su frecuencia. El retiro se registra desde Liquidación de contrato."
      endpoint="/api/nomina/empleados"
      modulo="nomina"
      columns={[
        { key: "nombre", label: "Empleado", render: (r) => [r.primer_nombre, r.otros_nombres, r.primer_apellido, r.segundo_apellido].filter(Boolean).join(" ") },
        { key: "numero_documento", label: "Documento", render: (r) => `${r.tipo_documento || "CC"} ${r.numero_documento}` },
        { key: "salario_basico", label: "Salario", render: (r) => fmtCOP(r.salario_basico) },
        { key: "tipo_contrato", label: "Contrato", render: (r) => etiquetaDe(CONTRATOS, r.tipo_contrato) },
        { key: "frecuencia_pago", label: "Pago", render: (r) => etiquetaDe(FRECUENCIAS, r.frecuencia_pago) },
        { key: "fecha_ingreso", label: "Ingreso" },
        { key: "estado", label: "Estado", render: (r) => (r.estado === "retirado" ? `Retirado ${r.fecha_retiro || ""}` : "Activo") },
      ]}
      fields={[
        { seccion: "Datos personales" },
        { key: "tipo_documento", label: "Tipo de documento", type: "select", options: DOCUMENTOS, defecto: "CC" },
        { key: "numero_documento", label: "Número de documento", required: true },
        { key: "primer_nombre", label: "Primer nombre", required: true },
        { key: "otros_nombres", label: "Otros nombres" },
        { key: "primer_apellido", label: "Primer apellido", required: true },
        { key: "segundo_apellido", label: "Segundo apellido" },
        { key: "email", label: "Email", type: "email" },
        { key: "direccion", label: "Dirección" },
        { key: "ciudad", label: "Ciudad" },

        { seccion: "Contrato y salario" },
        { key: "fecha_ingreso", label: "Fecha de ingreso", type: "date", required: true },
        { key: "tipo_contrato", label: "Tipo de contrato", type: "select", options: CONTRATOS, defecto: "indefinido", required: true },
        { key: "frecuencia_pago", label: "Frecuencia de pago", type: "select", options: FRECUENCIAS, defecto: "mensual", required: true,
          hint: "Si pagas quincenal, la nómina electrónica igual se envía consolidada por mes." },
        { key: "salario_basico", label: "Salario básico mensual", type: "number", required: true },
        { key: "salario_integral", label: "Salario integral", type: "checkbox", defecto: false, textoCheckbox: "Sí (sin prestaciones; cotiza sobre el 70%)" },
        { key: "tiempo_parcial", label: "Tiempo parcial", type: "checkbox", defecto: false, textoCheckbox: "Sí (permite salario menor al mínimo)" },
        { key: "riesgo_arl", label: "Nivel de riesgo ARL", type: "select", options: RIESGOS, defecto: "I", required: true },

        { seccion: "Afiliaciones" },
        { key: "eps", label: "EPS" },
        { key: "afp", label: "Fondo de pensiones" },
        { key: "arl", label: "ARL" },
        { key: "caja", label: "Caja de compensación" },
        { key: "fondo_cesantias", label: "Fondo de cesantías" },

        { seccion: "Pago", hint: "Datos que se reportan a la DIAN en la nómina electrónica." },
        { key: "banco", label: "Banco" },
        { key: "tipo_cuenta", label: "Tipo de cuenta", type: "select", options: CUENTAS, defecto: "ahorros" },
        { key: "numero_cuenta", label: "Número de cuenta" },

        { seccion: "Retención en la fuente laboral", hint: "Deducciones que reducen la base de retención (procedimiento 1)." },
        { key: "dependientes", label: "Dependientes", type: "checkbox", defecto: false, textoCheckbox: "Tiene dependientes (deducción del 10%)" },
        { key: "deduccion_vivienda", label: "Intereses de vivienda (mensual)", type: "number" },
        { key: "medicina_prepagada", label: "Medicina prepagada (mensual)", type: "number" },
      ]}
    />
  );
}
