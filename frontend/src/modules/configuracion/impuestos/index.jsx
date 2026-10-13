import ResourceCrud from "../../_ResourceCrud.jsx";

export default function Page() {
  return (
    <ResourceCrud
      titulo="Impuesto al consumo"
      descripcion="Crea cada impuesto al consumo (INC) con su tarifa y la cuenta contable donde se causa. Luego asígnalo a los productos que lo generan: se calcula y se contabiliza con la factura."
      endpoint="/api/configuracion/impuestos"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "tarifa", label: "Tarifa", render: (r) => `${r.tarifa} %` },
        { key: "cuenta_contable", label: "Cuenta contable" },
      ]}
      fields={[
        { key: "nombre", label: "Nombre", required: true, hint: "Ej.: INC restaurantes 8%" },
        { key: "tarifa", label: "Tarifa (%)", type: "number", required: true },
        {
          key: "cuenta_contable",
          label: "Cuenta contable del impuesto",
          type: "cuenta",
          prefijos: ["24"],
          required: true,
          hint: "Cuenta de pasivo donde se causa (p. ej. 2495). Créala en Plan de cuentas si necesitas una subcuenta.",
        },
      ]}
    />
  );
}
