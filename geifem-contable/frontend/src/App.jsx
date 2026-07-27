import { Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./shared/auth/ProtectedRoute.jsx";
import AppLayout from "./shared/layout/AppLayout.jsx";
import LoginPage from "./shared/auth/LoginPage.jsx";

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

// Contabilidad
import ComprobanteAjuste from "./modules/contabilidad/comprobante-ajuste/index.jsx";
import NotasContables from "./modules/contabilidad/notas-contables/index.jsx";
import ComprobanteApertura from "./modules/contabilidad/comprobante-apertura/index.jsx";
import ComprobanteCierre from "./modules/contabilidad/comprobante-cierre/index.jsx";
import ConsultaComprobantes from "./modules/contabilidad/consulta-comprobantes/index.jsx";
import AuditoriaComprobantes from "./modules/contabilidad/auditoria-comprobantes/index.jsx";

// Facturación
import FacturaVenta from "./modules/facturacion/factura-venta/index.jsx";
import DocumentoEquivalentePos from "./modules/facturacion/documento-equivalente-pos/index.jsx";
import NotasCreditoDebito from "./modules/facturacion/notas-credito-debito/index.jsx";

// Inventario
import CatalogoProductos from "./modules/inventario/catalogo-productos/index.jsx";
import KardexPP from "./modules/inventario/kardex-promedio-ponderado/index.jsx";
import SyncPosOnline from "./modules/inventario/sync-pos-online/index.jsx";

// Reportes
import Form300Iva from "./modules/reportes/form-300-iva/index.jsx";
import Form260Simple from "./modules/reportes/form-260-simple/index.jsx";
import EstadosFinancieros from "./modules/reportes/estados-financieros/index.jsx";
import Form350 from "./modules/reportes/form-350-retenciones/index.jsx";
import LibrosOficiales from "./modules/reportes/libros-oficiales/index.jsx";
import Exogena from "./modules/reportes/exogena/index.jsx";

// Compras (F2 placeholders)
import OrdenesCompra from "./modules/compras/ordenes-compra/index.jsx";
import RecepcionMercancia from "./modules/compras/recepcion-mercancia/index.jsx";
import FacturasProveedor from "./modules/compras/facturas-proveedor/index.jsx";
import ComprasRetenciones from "./modules/compras/retenciones/index.jsx";

// Tesorería (F2/F3 placeholders)
import Caja from "./modules/tesoreria/caja/index.jsx";
import Bancos from "./modules/tesoreria/bancos/index.jsx";
import CxcCxp from "./modules/tesoreria/cxc-cxp/index.jsx";
import FlujoCaja from "./modules/tesoreria/flujo-caja/index.jsx";
import ConciliacionAuto from "./modules/tesoreria/conciliacion-bancaria-auto/index.jsx";

function Home() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-geifem-navy mb-2">GEIFEM Contable</h1>
      <p className="text-slate-600">
        Sistema contable multi-tenant. Selecciona una empresa en la barra superior y
        navega los módulos desde el menú lateral.
      </p>
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
          <Route path="plan-cuentas" element={<PlanCuentas />} />
          <Route path="terceros" element={<Terceros />} />
          <Route path="tipos-documento" element={<TiposDocumento />} />
          <Route path="resoluciones-dian" element={<ResolucionesDian />} />
          <Route path="centros-costo" element={<CentrosCosto />} />
          <Route path="impuestos" element={<Impuestos />} />
          <Route path="unidades-medida" element={<UnidadesMedida />} />
          <Route path="formas-pago" element={<FormasPago />} />
          <Route path="usuarios-roles" element={<UsuariosRoles />} />
          <Route path="datos-empresa" element={<DatosEmpresa />} />
        </Route>

        <Route path="contabilidad">
          <Route path="comprobante-ajuste" element={<ComprobanteAjuste />} />
          <Route path="notas-contables" element={<NotasContables />} />
          <Route path="comprobante-apertura" element={<ComprobanteApertura />} />
          <Route path="comprobante-cierre" element={<ComprobanteCierre />} />
          <Route path="consulta-comprobantes" element={<ConsultaComprobantes />} />
          <Route path="auditoria-comprobantes" element={<AuditoriaComprobantes />} />
        </Route>

        <Route path="facturacion">
          <Route path="factura-venta" element={<FacturaVenta />} />
          <Route path="documento-equivalente-pos" element={<DocumentoEquivalentePos />} />
          <Route path="notas-credito-debito" element={<NotasCreditoDebito />} />
        </Route>

        <Route path="inventario">
          <Route path="catalogo-productos" element={<CatalogoProductos />} />
          <Route path="kardex-promedio-ponderado" element={<KardexPP />} />
          <Route path="sync-pos-online" element={<SyncPosOnline />} />
        </Route>

        <Route path="reportes">
          <Route path="form-300-iva" element={<Form300Iva />} />
          <Route path="form-260-simple" element={<Form260Simple />} />
          <Route path="estados-financieros" element={<EstadosFinancieros />} />
          <Route path="form-350-retenciones" element={<Form350 />} />
          <Route path="libros-oficiales" element={<LibrosOficiales />} />
          <Route path="exogena" element={<Exogena />} />
        </Route>

        <Route path="compras">
          <Route path="ordenes-compra" element={<OrdenesCompra />} />
          <Route path="recepcion-mercancia" element={<RecepcionMercancia />} />
          <Route path="facturas-proveedor" element={<FacturasProveedor />} />
          <Route path="retenciones" element={<ComprasRetenciones />} />
        </Route>

        <Route path="tesoreria">
          <Route path="caja" element={<Caja />} />
          <Route path="bancos" element={<Bancos />} />
          <Route path="cxc-cxp" element={<CxcCxp />} />
          <Route path="flujo-caja" element={<FlujoCaja />} />
          <Route path="conciliacion-bancaria-auto" element={<ConciliacionAuto />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
