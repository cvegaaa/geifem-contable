import CuentasTesoreria from "../_CuentasTesoreria.jsx";

export default function Page() {
  return (
    <CuentasTesoreria
      tipo="banco"
      titulo="Bancos"
      endpointCatalogo="/api/tesoreria/cuentas-bancarias"
      endpointSaldos="/api/tesoreria/bancos"
    />
  );
}
