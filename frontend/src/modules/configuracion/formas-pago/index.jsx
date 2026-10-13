import ResourceCrud, { etiquetaDe } from "../../_ResourceCrud.jsx";

const TIPOS = [
  { valor: "efectivo", etiqueta: "Efectivo" },
  { valor: "transferencia", etiqueta: "Transferencia" },
  { valor: "tarjeta", etiqueta: "Tarjeta débito/crédito" },
  { valor: "nequi", etiqueta: "Nequi" },
  { valor: "daviplata", etiqueta: "Daviplata" },
  { valor: "credito", etiqueta: "Crédito (a plazo)" },
];

export default function Page() {
  return (
    <ResourceCrud
      titulo="Formas de pago"
      endpoint="/api/configuracion/formas-pago"
      modulo="configuracion"
      columns={[
        { key: "nombre", label: "Nombre" },
        { key: "tipo", label: "Tipo", render: (r) => etiquetaDe(TIPOS, r.tipo) },
      ]}
      fields={[
        { key: "nombre", label: "Nombre", required: true },
        { key: "tipo", label: "Tipo", type: "select", options: TIPOS, required: true },
      ]}
    />
  );
}
