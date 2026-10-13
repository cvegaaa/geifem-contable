/**
 * Mapa de navegación: la barra lateral muestra solo los módulos; al hacer
 * clic se abre la subpantalla del módulo con sus opciones como tarjetas.
 * `permiso` es el módulo de permisos que se exige para verlo.
 */
const MODULOS = [
  {
    slug: "configuracion",
    titulo: "Configuración",
    icono: "ajustes",
    permiso: "configuracion",
    descripcion: "Datos de la empresa, catálogos y usuarios.",
    items: [
      { to: "/configuracion/datos-empresa", titulo: "Datos de empresa", descripcion: "NIT, régimen, responsabilidad de IVA y datos de contacto." },
      { to: "/configuracion/terceros", titulo: "Terceros", descripcion: "Clientes, proveedores y otros contactos." },
      { to: "/configuracion/plan-cuentas", titulo: "Plan de cuentas", descripcion: "Cuentas del PUC de la empresa." },
      { to: "/configuracion/parametros-contables", titulo: "Cuentas por defecto", descripcion: "Cuentas de respaldo y comunes de los asientos automáticos; el ingreso, costo y retenciones se definen en cada producto y la nómina en cada empleado." },
      { to: "/configuracion/resoluciones-dian", titulo: "Resoluciones DIAN", descripcion: "Rangos de numeración autorizados para facturar." },
      { to: "/configuracion/conceptos-retencion", titulo: "Conceptos de retención", descripcion: "Tarifas y bases de ReteFuente, ReteICA y ReteIVA según tu perfil tributario." },
      { to: "/configuracion/impuestos", titulo: "Impuesto al consumo", descripcion: "Tarifas del INC y la cuenta contable donde se causa." },
      { to: "/configuracion/formas-pago", titulo: "Formas de pago", descripcion: "Efectivo, transferencia, tarjeta, Nequi…" },
      { to: "/configuracion/unidades-medida", titulo: "Unidades de medida", descripcion: "Unidades para tus productos." },
      { to: "/configuracion/centros-costo", titulo: "Centros de costo", descripcion: "Agrupa ingresos y gastos por área o proyecto." },
      { to: "/configuracion/tipos-documento", titulo: "Tipos de documento", descripcion: "Prefijos de documentos internos." },
      { to: "/configuracion/tarifas-simple", titulo: "Tarifas SIMPLE", descripcion: "Tarifas consolidadas del régimen SIMPLE por grupo de actividad." },
      { to: "/configuracion/importar-datos", titulo: "Importar datos", descripcion: "Carga terceros, productos y saldos iniciales desde Excel." },
      { to: "/configuracion/usuarios-roles", titulo: "Usuarios", descripcion: "Usuarios de la empresa, su rol y su estado." },
      { to: "/configuracion/roles-permisos", titulo: "Roles y permisos", descripcion: "Qué puede hacer cada rol en cada módulo y si requiere aprobación." },
    ],
  },
  {
    slug: "contabilidad",
    titulo: "Contabilidad",
    icono: "libro",
    permiso: "contabilidad",
    descripcion: "Comprobantes contables, consulta y auditoría.",
    items: [
      { to: "/contabilidad/comprobante-ajuste", titulo: "Comprobantes de ajuste", descripcion: "Ajustes y reclasificaciones (CA)." },
      { to: "/contabilidad/notas-contables", titulo: "Notas contables", descripcion: "Registros contables generales (NT)." },
      { to: "/contabilidad/comprobante-apertura", titulo: "Apertura", descripcion: "Saldos iniciales de la empresa (AP)." },
      { to: "/contabilidad/comprobante-cierre", titulo: "Cierre", descripcion: "Cierre de cuentas de resultado (CC)." },
      { to: "/contabilidad/consulta-comprobantes", titulo: "Consulta de comprobantes", descripcion: "Busca, revisa, edita o anula cualquier comprobante." },
      { to: "/contabilidad/aprobaciones", titulo: "Aprobaciones", descripcion: "Autoriza o rechaza los documentos de quienes requieren aprobación." },
      { to: "/contabilidad/cierre-periodos", titulo: "Cierre de periodos", descripcion: "Bloquea los meses ya declarados para que nadie modifique su contabilidad." },
      { to: "/contabilidad/auditoria-comprobantes", titulo: "Auditoría", descripcion: "Historial de quién creó, editó o anuló cada documento." },
    ],
  },
  {
    slug: "facturacion",
    titulo: "Facturación",
    icono: "factura",
    permiso: "facturacion",
    descripcion: "Ventas: facturas, POS y notas.",
    items: [
      { to: "/facturacion/factura-venta", titulo: "Facturas de venta", descripcion: "Factura a crédito o contado con numeración DIAN." },
      { to: "/facturacion/documento-equivalente-pos", titulo: "Documento POS", descripcion: "Ventas de mostrador de contado (POS)." },
      { to: "/facturacion/notas-credito-debito", titulo: "Notas crédito y débito", descripcion: "Devoluciones, descuentos y ajustes a facturas." },
    ],
  },
  {
    slug: "inventario",
    titulo: "Inventario",
    icono: "caja",
    permiso: "inventario",
    descripcion: "Productos, bodegas y kardex.",
    items: [
      { to: "/inventario/catalogo-productos", titulo: "Productos y servicios", descripcion: "Catálogo de lo que compras y vendes." },
      { to: "/inventario/bodegas", titulo: "Bodegas", descripcion: "Lugares donde guardas tu mercancía." },
      { to: "/inventario/kardex-promedio-ponderado", titulo: "Kardex y ajustes", descripcion: "Existencias, costo promedio y ajustes manuales." },
    ],
  },
  {
    slug: "compras",
    titulo: "Compras",
    icono: "carrito",
    permiso: "compras",
    descripcion: "Órdenes, entradas de mercancía y facturas de proveedor.",
    items: [
      { to: "/compras/ordenes-compra", titulo: "Órdenes de compra", descripcion: "Pedidos a proveedores (OC)." },
      { to: "/compras/recepcion-mercancia", titulo: "Entradas de mercancía", descripcion: "Mercancía recibida en bodega (EM)." },
      { to: "/compras/facturas-proveedor", titulo: "Facturas de proveedor", descripcion: "Compras y gastos con retenciones (FP)." },
      { to: "/compras/facturas-recibidas", titulo: "Facturas electrónicas recibidas", descripcion: "Carga el XML del proveedor, registra los eventos RADIAN y contabiliza." },
      { to: "/compras/devoluciones-proveedor", titulo: "Devoluciones a proveedor", descripcion: "Devuelve mercancía o rebaja facturas de proveedor (NP)." },
      { to: "/compras/retenciones", titulo: "Retenciones practicadas", descripcion: "Resumen de retenciones por periodo." },
    ],
  },
  {
    slug: "tesoreria",
    titulo: "Tesorería",
    icono: "dinero",
    permiso: "tesoreria",
    descripcion: "Caja, bancos, cartera y flujo de caja.",
    items: [
      { to: "/tesoreria/caja", titulo: "Caja", descripcion: "Cajas y sus movimientos (MT)." },
      { to: "/tesoreria/bancos", titulo: "Bancos", descripcion: "Cuentas bancarias y sus movimientos (MT)." },
      { to: "/tesoreria/cxc-cxp", titulo: "Cartera y pagos", descripcion: "Cobros (RC) y pagos a proveedores (CE)." },
      { to: "/tesoreria/anticipos", titulo: "Anticipos", descripcion: "Anticipos de clientes y a proveedores y su aplicación a facturas." },
      { to: "/tesoreria/transferencias", titulo: "Transferencias", descripcion: "Traslados entre cajas y bancos (TR)." },
      { to: "/tesoreria/antiguedad-cartera", titulo: "Antigüedad de cartera", descripcion: "Cartera por edades y estado de cuenta por tercero." },
      { to: "/tesoreria/flujo-caja", titulo: "Flujo de caja", descripcion: "Ingresos y egresos por día." },
      { to: "/tesoreria/conciliacion-bancaria-auto", titulo: "Conciliación bancaria", descripcion: "Cruza el extracto con tus movimientos." },
    ],
  },
  {
    slug: "nomina",
    titulo: "Nómina",
    icono: "personas",
    permiso: "nomina",
    descripcion: "Empleados, liquidación mensual o quincenal, prestaciones, PILA y nómina electrónica.",
    items: [
      { to: "/nomina/empleados", titulo: "Empleados", descripcion: "Contratos, salarios, afiliaciones y datos de pago." },
      { to: "/nomina/novedades", titulo: "Novedades", descripcion: "Horas extra, incapacidades, licencias, vacaciones, comisiones y descuentos." },
      { to: "/nomina/periodos", titulo: "Liquidación de nómina", descripcion: "Liquida el mes o la quincena, imprime desprendibles y paga." },
      { to: "/nomina/prestaciones", titulo: "Prestaciones y seguridad social", descripcion: "Prima, cesantías, intereses, vacaciones y aportes (PILA)." },
      { to: "/nomina/liquidacion-contrato", titulo: "Liquidación de contrato", descripcion: "Retiro de un empleado: prestaciones, vacaciones e indemnización." },
      { to: "/nomina/electronica", titulo: "Nómina electrónica", descripcion: "Paquete mensual consolidado por empleado para la DIAN." },
      { to: "/nomina/parametros", titulo: "Parámetros de nómina", descripcion: "Salario mínimo, auxilio, UVT, recargos y porcentajes de aportes por año." },
    ],
  },
  {
    slug: "reportes",
    titulo: "Reportes",
    icono: "grafica",
    permiso: "reportes",
    descripcion: "Reportes de ventas, contables, financieros y fiscales.",
    // Las opciones salen del catálogo de reportes (subpantalla propia).
    items: [],
  },
];

export default MODULOS;

export function moduloDeRuta(pathname) {
  const slug = pathname.split("/")[1];
  return MODULOS.find((m) => m.slug === slug) || null;
}

export function opcionDeRuta(pathname) {
  const modulo = moduloDeRuta(pathname);
  if (!modulo) return null;
  return modulo.items.find((i) => pathname === i.to || pathname.startsWith(i.to + "/")) || null;
}
