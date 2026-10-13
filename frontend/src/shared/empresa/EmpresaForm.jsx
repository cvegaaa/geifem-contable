import FormField, { Input, Select } from "../layout/FormField/index.jsx";

export const EMPRESA_VACIA = {
  nit: "",
  dv: "",
  razon_social: "",
  regimen_tributario: "ORDINARIO",
  responsable_iva: true,
  ciudad: "",
  direccion: "",
  telefono: "",
  email: "",
  actividad_ciiu: "",
  grupo_simple: 2,
  gran_contribuyente: false,
  agente_retenedor: true,
  agente_reteiva: true,
  autorretenedor_renta: false,
  tarifa_autorretencion: 0.8,
  tarifa_reteica: 0,
};

/** Convierte "" en null para los campos opcionales antes de enviar al backend. */
export function empresaParaEnviar(e) {
  const salida = { ...e };
  for (const k of ["dv", "ciudad", "direccion", "telefono", "email", "actividad_ciiu"]) {
    if (typeof salida[k] === "string" && salida[k].trim() === "") salida[k] = null;
  }
  delete salida.id;
  delete salida.activo;
  delete salida.creado_por;
  delete salida.fecha_creacion;
  delete salida.fecha_actualizacion;
  return salida;
}

function Casilla({ texto, checked, onChange, disabled }) {
  return (
    <label className={`flex items-center gap-2 text-sm ${disabled ? "text-slate-400" : "text-slate-700"}`}>
      <input type="checkbox" checked={Boolean(checked)} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {texto}
    </label>
  );
}

export default function EmpresaForm({ value, onChange, disabled = false }) {
  const set = (campo, v) => onChange({ ...value, [campo]: v });
  const simple = value.regimen_tributario === "SIMPLE";

  // Art. 911 ET: el régimen SIMPLE no practica retención en la fuente ni se autorretiene
  // (salvo pagos laborales e IVA). Al cambiar de régimen se ajustan las opciones.
  const cambiarRegimen = (regimen) => {
    const esSimple = regimen === "SIMPLE";
    onChange({
      ...value,
      regimen_tributario: regimen,
      agente_retenedor: !esSimple,
      agente_reteiva: !esSimple && value.responsable_iva,
      autorretenedor_renta: esSimple ? false : value.autorretenedor_renta,
    });
  };
  const cambiarIva = (v) =>
    onChange({ ...value, responsable_iva: v, agente_reteiva: v ? value.agente_reteiva : false });
  return (
    <div className="grid grid-cols-1 sm:grid-cols-6 gap-x-3">
      <div className="sm:col-span-4">
        <FormField label="NIT" hint="Solo números, sin dígito de verificación">
          <Input
            required
            inputMode="numeric"
            value={value.nit}
            disabled={disabled}
            onChange={(e) => set("nit", e.target.value.replace(/\D/g, ""))}
          />
        </FormField>
      </div>
      <div className="sm:col-span-2">
        <FormField label="DV">
          <Input
            maxLength={1}
            inputMode="numeric"
            value={value.dv || ""}
            disabled={disabled}
            onChange={(e) => set("dv", e.target.value.replace(/\D/g, ""))}
          />
        </FormField>
      </div>
      <div className="sm:col-span-6">
        <FormField label="Razón social">
          <Input
            required
            value={value.razon_social}
            disabled={disabled}
            onChange={(e) => set("razon_social", e.target.value)}
          />
        </FormField>
      </div>
      <div className="sm:col-span-3">
        <FormField label="Régimen tributario">
          <Select
            value={value.regimen_tributario}
            disabled={disabled}
            onChange={(e) => cambiarRegimen(e.target.value)}
          >
            <option value="ORDINARIO">Ordinario</option>
            <option value="SIMPLE">SIMPLE (Régimen Simple de Tributación)</option>
          </Select>
        </FormField>
      </div>
      <div className="sm:col-span-3 flex items-center pt-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={Boolean(value.responsable_iva)}
            disabled={disabled}
            onChange={(e) => cambiarIva(e.target.checked)}
          />
          Responsable de IVA
        </label>
      </div>
      {simple && (
        <div className="sm:col-span-6">
          <FormField label="Grupo de actividad SIMPLE" hint="Define la tarifa consolidada del Formulario 2593 y del 260">
            <Select value={value.grupo_simple || 2} disabled={disabled} onChange={(e) => set("grupo_simple", Number(e.target.value))}>
              <option value={1}>1 · Tiendas pequeñas, mini-mercados, micro-mercados y peluquería</option>
              <option value={2}>2 · Comercio, servicios técnicos y mecánicos, industria y demás</option>
              <option value={3}>3 · Servicios profesionales, de consultoría y científicos</option>
              <option value={4}>4 · Comidas y bebidas, y transporte</option>
              <option value={5}>5 · Educación y salud humana</option>
            </Select>
          </FormField>
        </div>
      )}
      <div className="sm:col-span-3">
        <FormField label="Ciudad">
          <Input value={value.ciudad || ""} disabled={disabled} onChange={(e) => set("ciudad", e.target.value)} />
        </FormField>
      </div>
      <div className="sm:col-span-3">
        <FormField label="Actividad CIIU" hint="4 dígitos">
          <Input
            maxLength={4}
            inputMode="numeric"
            value={value.actividad_ciiu || ""}
            disabled={disabled}
            onChange={(e) => set("actividad_ciiu", e.target.value.replace(/\D/g, ""))}
          />
        </FormField>
      </div>
      <div className="sm:col-span-6">
        <FormField label="Dirección">
          <Input value={value.direccion || ""} disabled={disabled} onChange={(e) => set("direccion", e.target.value)} />
        </FormField>
      </div>
      <div className="sm:col-span-3">
        <FormField label="Teléfono">
          <Input value={value.telefono || ""} disabled={disabled} onChange={(e) => set("telefono", e.target.value)} />
        </FormField>
      </div>
      <div className="sm:col-span-3">
        <FormField label="Email de la empresa">
          <Input type="email" value={value.email || ""} disabled={disabled} onChange={(e) => set("email", e.target.value)} />
        </FormField>
      </div>

      <div className="sm:col-span-6 mt-2 pt-3 border-t border-slate-200">
        <h4 className="text-sm font-semibold text-geifem-navy">Perfil tributario</h4>
        <p className="text-xs text-slate-500 mb-2">
          Define qué impuestos y retenciones podrás parametrizar en productos y documentos.
          {simple && " Régimen SIMPLE (art. 911 ET): no te practican retención en la fuente ni la practicas (salvo pagos laborales); el ReteIVA sí aplica."}
        </p>
        <div className="grid sm:grid-cols-2 gap-x-4 gap-y-2">
          <Casilla texto="Gran contribuyente" checked={value.gran_contribuyente} disabled={disabled}
            onChange={(v) => set("gran_contribuyente", v)} />
          <Casilla texto="Agente de retención en la fuente (renta e ICA)" checked={value.agente_retenedor}
            disabled={disabled || simple} onChange={(v) => set("agente_retenedor", v)} />
          <Casilla texto="Agente de retención de IVA (ReteIVA)" checked={value.agente_reteiva}
            disabled={disabled || !value.responsable_iva} onChange={(v) => set("agente_reteiva", v)} />
          <Casilla texto="Autorretenedor especial de renta" checked={value.autorretenedor_renta}
            disabled={disabled || simple} onChange={(v) => set("autorretenedor_renta", v)} />
        </div>
        <div className="grid sm:grid-cols-2 gap-x-4 mt-2">
          {value.autorretenedor_renta && (
            <FormField label="Tarifa de autorretención (%)" hint="Según tu actividad económica (CIIU); típicamente 0,4% a 1,6%.">
              <Input type="number" step="any" min="0" value={value.tarifa_autorretencion} disabled={disabled}
                onChange={(e) => set("tarifa_autorretencion", Number(e.target.value))} />
            </FormField>
          )}
          {!simple && (
            <FormField label="Tarifa de ICA de tu municipio (por mil)" hint="Se usa para calcular el ReteICA que te practican en tus ventas.">
              <Input type="number" step="any" min="0" value={value.tarifa_reteica} disabled={disabled}
                onChange={(e) => set("tarifa_reteica", Number(e.target.value))} />
            </FormField>
          )}
        </div>
      </div>
    </div>
  );
}
