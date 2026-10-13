import { useEffect, useState } from "react";
import api from "../../../core/api.js";
import { useAuth } from "../../../shared/auth/AuthContext.jsx";
import FormField from "../../../shared/layout/FormField/index.jsx";
import { Avisos, SelectorCuenta, mensajeError } from "../../../shared/documentos/index.jsx";
import ResourceCrud from "../../_ResourceCrud.jsx";

/**
 * Impuesto nacional al consumo (INC): un solo impuesto con varias tarifas (4 %, 8 %, 16 %…) que se causa en una cuenta.
 * No incluye el ICA, que es un impuesto municipal distinto (su tarifa va en Datos de la empresa y sus retenciones en
 * Conceptos de retención).
 */
export default function Page() {
  const { puede } = useAuth();
  const [plan, setPlan] = useState([]);
  const [cuenta, setCuenta] = useState("");
  const [aviso, setAviso] = useState({});
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api.get("/api/configuracion/plan-cuentas").then((r) => setPlan(r.data.filter((c) => String(c.codigo).startsWith("24")))).catch(() => {});
    api.get("/api/configuracion/impuesto-consumo/cuenta").then((r) => setCuenta(r.data.cuenta_contable)).catch(() => {});
  }, []);

  const guardarCuenta = async (codigo) => {
    setCuenta(codigo);
    if (!codigo) return;
    try {
      await api.put("/api/configuracion/impuesto-consumo/cuenta", { cuenta_contable: codigo });
      setAviso({ mensaje: "Cuenta del impuesto al consumo actualizada" });
      setVersion((v) => v + 1);
    } catch (err) {
      setAviso({ error: mensajeError(err) });
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-bold text-geifem-navy mb-1">Impuesto al consumo (INC)</h1>
      <p className="text-sm text-slate-500 mb-3">
        Es un solo impuesto con varias tarifas. Define la cuenta donde se causa y las tarifas que usas; luego asigna la tarifa a cada producto que lo genera
        (se calcula y se contabiliza con la factura). El ICA es un impuesto distinto: su tarifa va en Datos de la empresa y sus retenciones en Conceptos de retención.
      </p>
      <Avisos error={aviso.error} mensaje={aviso.mensaje} />
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4 max-w-xl">
        <FormField label="Cuenta contable del impuesto al consumo" hint="Cuenta de pasivo (24xx) donde se causa; vale para todas las tarifas.">
          <SelectorCuenta cuentas={plan} porCodigo value={cuenta} disabled={!puede("configuracion", "editar")} onChange={guardarCuenta} />
        </FormField>
      </div>
      <ResourceCrud
        key={version}
        titulo="Tarifas del impuesto al consumo"
        descripcion=""
        endpoint="/api/configuracion/impuestos"
        modulo="configuracion"
        columns={[
          { key: "nombre", label: "Tarifa" },
          { key: "tarifa", label: "Porcentaje", render: (r) => `${r.tarifa} %` },
        ]}
        fields={[
          { key: "nombre", label: "Nombre", required: true, hint: "Ej.: Restaurantes y bares 8 %" },
          { key: "tarifa", label: "Tarifa (%)", type: "number", required: true },
        ]}
      />
    </div>
  );
}
