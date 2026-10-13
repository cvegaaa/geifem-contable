import { Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./shared/auth/ProtectedRoute.jsx";
import AppLayout from "./shared/layout/AppLayout.jsx";
import LoginPage from "./shared/auth/LoginPage.jsx";
import ModuloHub, { TarjetasModulos } from "./shared/layout/ModuloHub.jsx";
import { useEmpresa } from "./core/EmpresaContext.jsx";
import { useAuth } from "./shared/auth/AuthContext.jsx";

// Configuración
import PlanCuentas from "./modules/configuracion/plan-cuentas/index.jsx";
import Terceros from "./modules/configuracion/terceros/index.jsx";
import TiposDocumento from "./modules/configuracion/tipos-documento/index.jsx";
import ResolucionesDian from "./modules/configuracion/resoluciones-dian/index.jsx";
import CentrosCosto from "./modules/configuracion/centros-costo/index.jsx";
import Impuestos from "./modules/configuracion/impuestos/index.jsx";
import UnidadesMedida from "./modules/configuracion/unidades-medida/index.jsx";
import FormasPago from "./modules/configuracion/formas-pago/index.jsx";
import UsuariosRoles from "./modules/configuracion/usuarios-roles/index.jsx";
import DatosEmpresa from "./modules/configuracion/datos-empresa/index.jsx";
import ConceptosRetencion from "./modules/configuracion/conceptos-retencion/index.jsx";
import TarifasSimple from "./modules/configuracion/tarifas-simple/index.jsx";
import ImportarDatos from "./modules/configuracion/importar-datos/index.jsx";
import ParametrosContables from "./modules/configuracion/parametros-contables/index.jsx";

// Contabilidad
import ComprobanteAjuste from "./modules/contabilidad/comprobante-ajuste/index.jsx";
import NotasContables from "./modules/contabilidad/notas-contables/index.jsx";
import ComprobanteApertura from "./modules/contabilidad/comprobante-apertura/index.jsx";
import ComprobanteCierre from "./modules/contabilidad/comprobante-cierre/index.jsx";
import ConsultaComprobantes from "./modules/contabilidad/consulta-comprobantes/index.jsx";
import CierrePeriodos from "./modules/contabilidad/cierre-periodos/index.jsx";
import AuditoriaComprobantes from "./modules/contabilidad/auditoria-comprobantes/index.jsx";

// Facturación
import FacturaVenta from "./modules/facturacion/factura-venta/index.jsx";
import DocumentoEquivalentePos from "./modules/facturacion/documento-equivalente-pos/index.jsx";
import NotasCreditoDebito from "./modules/facturacion/notas-credito-debito/index.jsx";

// Inventario
import CatalogoProductos from "./modules/inventario/catalogo-productos/index.jsx";
import Bodegas from "./modules/inventario/bodegas/index.jsx";
import KardexPP from "./modules/inventario/kardex-promedio-ponderado/index.jsx";

// Nómina
import Empleados from "./modules/nomina/empleados/index.jsx";
import Novedades from "./modules/nomina/novedades/index.jsx";
import PeriodosNomina from "./modules/nomina/periodos/index.jsx";
import Prestaciones from "./modules/nomina/prestaciones/index.jsx";
import LiquidacionContrato from "./modules/nomina/liquidacion-contrato/index.jsx";
import NominaElectronica from "./modules/nomina/electronica/index.jsx";
import ParametrosNomina from "./modules/nomina/parametros/index.jsx";

// Reportes
import IndiceReportes, { CategoriaReportes } from "./modules/reportes/index.jsx";
import VistaReporte from "./modules/reportes/_VistaReporte.jsx";
import Form350 from "./modules/reportes/form-350-retenciones/index.jsx";
import LibrosOficiales from "./modules/reportes/libros-oficiales/index.jsx";
import Exogena from "./modules/reportes/exogena/index.jsx";
import CalendarioTributario from "./modules/reportes/calendario-tributario/index.jsx";

// Compras
import OrdenesCompra from "./modules/compras/ordenes-compra/index.jsx";
import RecepcionMercancia from "./modules/compras/recepcion-mercancia/index.jsx";
import FacturasProveedor from "./modules/compras/facturas-proveedor/index.jsx";
import ComprasRetenciones from "./modules/compras/retenciones/index.jsx";

// Tesorería
import Caja from "./modules/tesoreria/caja/index.jsx";
import Bancos from "./modules/tesoreria/bancos/index.jsx";
import AntiguedadCartera from "./modules/tesoreria/antiguedad-cartera/index.jsx";
import FacturasRecibidas from "./modules/compras/facturas-recibidas/index.jsx";
import DevolucionesProveedor from "./modules/compras/devoluciones-proveedor/index.jsx";
import Anticipos from "./modules/tesoreria/anticipos/index.jsx";
import Transferencias from "./modules/tesoreria/transferencias/index.jsx";
import CxcCxp from "./modules/tesoreria/cxc-cxp/index.jsx";
import FlujoCaja from "./modules/tesoreria/flujo-caja/index.jsx";
import ConciliacionAuto from "./modules/tesoreria/conciliacion-bancaria-auto/index.jsx";

function Home() {
  const { empresaActiva } = useEmpresa();
  const { puede } = useAuth();
  if (!empresaActiva) {
    return (
      <p className="text-slate-600">
        Aún no tienes acceso a ninguna empresa. Pide a un administrador que te asigne una.
      </p>
    );
  }
  return (
    <div>
      <h1 className="text-2xl font-bold text-geifem-navy mb-1">{empresaActiva.razon_social}</h1>
      <p className="text-slate-500 mb-6">NIT {empresaActiva.nit} · Elige un módulo para empezar.</p>
      <TarjetasModulos puede={puede} />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Home />} />

        <Route path="configuracion">
          <Route index element={<ModuloHub slug="configuracion" />} />
          <Route path="datos-empresa" element={<DatosEmpresa />} />
          <Route path="terceros" element={<Terceros />} />
          <Route path="plan-cuentas" element={<PlanCuentas />} />
          <Route path="parametros-contables" element={<ParametrosContables />} />
          <Route path="conceptos-retencion" element={<ConceptosRetencion />} />
          <Route path="tarifas-simple" element={<TarifasSimple />} />
          <Route path="importar-datos" element={<ImportarDatos />} />
          <Route path="resoluciones-dian" element={<ResolucionesDian />} />
          <Route path="impuestos" element={<Impuestos />} />
          <Route path="formas-pago" element={<FormasPago />} />
          <Route path="unidades-medida" element={<UnidadesMedida />} />
          <Route path="centros-costo" element={<CentrosCosto />} />
          <Route path="tipos-documento" element={<TiposDocumento />} />
          <Route path="usuarios-roles" element={<UsuariosRoles />} />
        </Route>

        <Route path="contabilidad">
          <Route index element={<ModuloHub slug="contabilidad" />} />
          <Route path="comprobante-ajuste" element={<ComprobanteAjuste />} />
          <Route path="notas-contables" element={<NotasContables />} />
          <Route path="comprobante-apertura" element={<ComprobanteApertura />} />
          <Route path="comprobante-cierre" element={<ComprobanteCierre />} />
          <Route path="consulta-comprobantes" element={<ConsultaComprobantes />} />
          <Route path="cierre-periodos" element={<CierrePeriodos />} />
          <Route path="auditoria-comprobantes" element={<AuditoriaComprobantes />} />
        </Route>

        <Route path="facturacion">
          <Route index element={<ModuloHub slug="facturacion" />} />
          <Route path="factura-venta" element={<FacturaVenta />} />
          <Route path="documento-equivalente-pos" element={<DocumentoEquivalentePos />} />
          <Route path="notas-credito-debito" element={<NotasCreditoDebito />} />
        </Route>

        <Route path="inventario">
          <Route index element={<ModuloHub slug="inventario" />} />
          <Route path="catalogo-productos" element={<CatalogoProductos />} />
          <Route path="bodegas" element={<Bodegas />} />
          <Route path="kardex-promedio-ponderado" element={<KardexPP />} />
        </Route>

        <Route path="compras">
          <Route index element={<ModuloHub slug="compras" />} />
          <Route path="ordenes-compra" element={<OrdenesCompra />} />
          <Route path="recepcion-mercancia" element={<RecepcionMercancia />} />
          <Route path="devoluciones-proveedor" element={<DevolucionesProveedor />} />
          <Route path="facturas-recibidas" element={<FacturasRecibidas />} />
          <Route path="facturas-proveedor" element={<FacturasProveedor />} />
          <Route path="retenciones" element={<ComprasRetenciones />} />
        </Route>

        <Route path="tesoreria">
          <Route index element={<ModuloHub slug="tesoreria" />} />
          <Route path="caja" element={<Caja />} />
          <Route path="bancos" element={<Bancos />} />
          <Route path="cxc-cxp" element={<CxcCxp />} />
          <Route path="anticipos" element={<Anticipos />} />
          <Route path="transferencias" element={<Transferencias />} />
          <Route path="antiguedad-cartera" element={<AntiguedadCartera />} />
          <Route path="flujo-caja" element={<FlujoCaja />} />
          <Route path="conciliacion-bancaria-auto" element={<ConciliacionAuto />} />
        </Route>

        <Route path="nomina">
          <Route index element={<ModuloHub slug="nomina" />} />
          <Route path="empleados" element={<Empleados />} />
          <Route path="novedades" element={<Novedades />} />
          <Route path="periodos" element={<PeriodosNomina />} />
          <Route path="prestaciones" element={<Prestaciones />} />
          <Route path="liquidacion-contrato" element={<LiquidacionContrato />} />
          <Route path="electronica" element={<NominaElectronica />} />
          <Route path="parametros" element={<ParametrosNomina />} />
        </Route>

        <Route path="reportes">
          <Route index element={<IndiceReportes />} />
          <Route path="form-350-retenciones" element={<Form350 />} />
          <Route path="libros-oficiales" element={<LibrosOficiales />} />
          <Route path="exogena" element={<Exogena />} />
          <Route path="calendario-tributario" element={<CalendarioTributario />} />
          <Route path=":categoria" element={<CategoriaReportes />} />
          <Route path=":categoria/:slug" element={<VistaReporte />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
