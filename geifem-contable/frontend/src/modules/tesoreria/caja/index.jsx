import CuentasTesoreria from "../_CuentasTesoreria.jsx";

export default function Page() {
  return (
    <CuentasTesoreria
      tipo="caja"
      titulo="Caja"
      endpointCatalogo="/api/tesoreria/cuentas-caja"
      endpointSaldos="/api/tesoreria/caja"
    />
  );
}
