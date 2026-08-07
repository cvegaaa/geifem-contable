/**
 * Catálogo de reportes por categoría (espejo del backend `api/reportes`).
 * estado: "activo" | "fase2" | "fase3"
 */
const CATALOGO = [
  {
    slug: "ventas",
    titulo: "Ventas",
    descripcion:
      "Monitorea la distribución de tus ventas y obtén información para gestionar tus operaciones comerciales.",
    reportes: [
      { slug: "ventas-generales", titulo: "Ventas generales", descripcion: "Revisa el desempeño de tus ventas para crear estrategias comerciales.", estado: "activo" },
      { slug: "ventas-por-item", titulo: "Ventas por ítem", descripcion: "Consulta tus ventas detalladas por cada ítem o servicio.", estado: "activo" },
      { slug: "ventas-por-cliente", titulo: "Ventas por cliente", descripcion: "Conoce las ventas asociadas a cada uno de tus clientes.", estado: "activo" },
      { slug: "rentabilidad-por-item", titulo: "Rentabilidad por ítem", descripcion: "Conoce la utilidad que generan tus ítems inventariables.", estado: "activo" },
      { slug: "ventas-por-vendedor", titulo: "Ventas por vendedor", descripcion: "Revisa el resumen de las ventas asociadas a cada vendedor/a.", estado: "fase2" },
      { slug: "estado-cuenta-por-cliente", titulo: "Estado de cuenta por cliente", descripcion: "Revisa el detalle de las ventas asociadas a cada cliente.", estado: "activo" },
      { slug: "ventas-diarias", titulo: "Ventas diarias", descripcion: "Exporta tus ventas agrupadas por forma de pago y numeraciones.", estado: "activo", exporta: "Excel" },
    ],
  },
  {
    slug: "administrativos",
    titulo: "Administrativos",
    descripcion:
      "Haz seguimiento a tus transacciones y obtén información para controlar la salud financiera de tu empresa.",
    reportes: [
      { slug: "cuentas-por-cobrar", titulo: "Cuentas por cobrar", descripcion: "Controla el vencimiento y cobro de tus facturas a crédito.", estado: "activo" },
      { slug: "cuentas-por-pagar", titulo: "Cuentas por pagar", descripcion: "Controla tus deudas registradas y pagos pendientes a proveedores.", estado: "activo" },
      { slug: "ingresos-y-gastos", titulo: "Ingresos y gastos", descripcion: "Conoce los valores asociados a tus cuentas de ingresos y egresos.", estado: "activo" },
      { slug: "valor-inventario", titulo: "Valor de inventario", descripcion: "Consulta el valor actual, cantidad y costo promedio de tu inventario.", estado: "activo" },
      { slug: "transacciones", titulo: "Transacciones", descripcion: "Consulta los movimientos de dinero registrados en tu contabilidad.", estado: "activo" },
      { slug: "compras", titulo: "Compras", descripcion: "Consulta las facturas de compra que tienes registradas en tu cuenta.", estado: "activo" },
      { slug: "reporte-anual", titulo: "Reporte anual", descripcion: "Conoce el rendimiento que ha tenido tu negocio en cada año.", estado: "activo" },
    ],
  },
  {
    slug: "financieros",
    titulo: "Financieros",
    descripcion:
      "Analiza los resultados financieros de tu empresa, incluyendo entradas y salidas de efectivo.",
    reportes: [
      { slug: "flujo-de-caja", titulo: "Flujo de caja", descripcion: "Revisa la evolución de tus movimientos de efectivo y conoce la liquidez de tu empresa.", estado: "activo" },
    ],
  },
  {
    slug: "contables",
    titulo: "Contables",
    descripcion:
      "Conoce el desempeño contable y el estado económico de tu empresa en todo momento.",
    reportes: [
      { slug: "estado-de-resultados", titulo: "Estado de resultados", descripcion: "Conoce el desempeño financiero de tu empresa.", estado: "activo" },
      { slug: "estado-situacion-financiera", titulo: "Estado de situación financiera", descripcion: "Conoce los recursos que tienes y cómo se están aprovechando.", estado: "activo" },
      { slug: "movimientos-por-cuenta-contable", titulo: "Movimientos por cuenta contable", descripcion: "Conoce la actividad de tus cuentas y sus movimientos asociados.", estado: "activo" },
      { slug: "libro-diario", titulo: "Libro diario", descripcion: "Gestiona el movimiento contable de tus transacciones registradas.", estado: "activo" },
      { slug: "auxiliar-por-tercero", titulo: "Auxiliar por tercero", descripcion: "Consulta el saldo acumulado de tus cuentas por cada contacto.", estado: "activo" },
      { slug: "balance-de-prueba", titulo: "Balance de prueba", descripcion: "Consulta el saldo acumulado y los movimientos de tus cuentas.", estado: "activo" },
      { slug: "balance-de-prueba-por-tercero", titulo: "Balance de prueba por tercero", descripcion: "Consulta los movimientos de tus cuentas detallados por contacto.", estado: "activo", exporta: "Excel" },
      { slug: "libro-mayor-y-balances", titulo: "Libro mayor y balances", descripcion: "Consulta los movimientos y balances detallados de tus cuentas.", estado: "activo", exporta: "PDF + 1" },
    ],
  },
  {
    slug: "fiscales",
    titulo: "Fiscales",
    descripcion:
      "Revisa el detalle de tus impuestos y retenciones para cumplir con tus obligaciones tributarias.",
    reportes: [
      { slug: "reporte-detallado-de-impuestos", titulo: "Reporte detallado de impuestos", descripcion: "Revisa el detalle de tus impuestos generados por cada transacción.", estado: "activo" },
      { slug: "impuestos-y-retenciones", titulo: "Impuestos y retenciones", descripcion: "Revisa los impuestos y retenciones asociados a tus ventas y compras.", estado: "activo" },
      { slug: "comprobante-informe-diario", titulo: "Comprobante de informe diario", descripcion: "Exporta el resumen de tus facturas registradas en tu punto de venta.", estado: "activo", exporta: "Excel" },
      { slug: "form-300-iva", titulo: "Formulario 300 — IVA", descripcion: "Declaración del impuesto sobre las ventas.", estado: "activo" },
      { slug: "form-260-simple", titulo: "Formulario 260 — SIMPLE", descripcion: "Recibo electrónico del régimen simple de tributación.", estado: "activo" },
      { slug: "formulario-350", titulo: "Formulario 350", descripcion: "Declaración retenciones en la fuente.", estado: "activo" },
    ],
  },
  {
    slug: "para-trabajar",
    titulo: "Para trabajar",
    descripcion: "Exporta la información clave de tu negocio para realizar análisis adicionales.",
    reportes: [
      { slug: "exportar-facturas", titulo: "Exportar facturas", descripcion: "Descarga el listado detallado de tus documentos de venta.", estado: "activo", exporta: "Excel" },
      { slug: "informe-contador", titulo: "Informe contador", descripcion: "Exporta la información detallada de tus ventas, gastos y más.", estado: "activo", exporta: "Excel" },
      { slug: "informe-de-mandatos", titulo: "Informe de mandatos", descripcion: "Exporta el detalle de tus ventas que incluyen ingresos para terceros.", estado: "fase3", exporta: "Excel" },
    ],
  },
  {
    slug: "exogena",
    titulo: "Información exógena",
    descripcion: "Gestiona tus formatos de información exógena para presentarlos ante la DIAN.",
    reportes: [
      { slug: "formato-1001", titulo: "Formato 1001", descripcion: "Pagos o abonos en cuenta y retenciones practicadas.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1003", titulo: "Formato 1003", descripcion: "Retenciones en la fuente que te practicaron.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1005", titulo: "Formato 1005", descripcion: "Impuesto a las ventas por pagar (descontable).", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1006", titulo: "Formato 1006", descripcion: "Impuesto a las ventas por pagar (generado) e impuesto al consumo.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1007", titulo: "Formato 1007", descripcion: "Ingresos recibidos en el año.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1008", titulo: "Formato 1008", descripcion: "Saldo de cuentas por cobrar.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-1009", titulo: "Formato 1009", descripcion: "Saldo de cuentas por pagar.", estado: "fase3", exporta: "Excel" },
      { slug: "formato-2276", titulo: "Formato 2276", descripcion: "Información de ingresos y retenciones por renta de trabajo y pensiones.", estado: "fase3", exporta: "Excel" },
    ],
  },
];

export function buscarCategoria(slug) {
  return CATALOGO.find((c) => c.slug === slug) || null;
}

export function buscarReporte(catSlug, repSlug) {
  const cat = buscarCategoria(catSlug);
  if (!cat) return { categoria: null, reporte: null };
  return { categoria: cat, reporte: cat.reportes.find((r) => r.slug === repSlug) || null };
}

export default CATALOGO;
