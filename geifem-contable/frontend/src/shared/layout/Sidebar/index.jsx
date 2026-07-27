import { NavLink } from "react-router-dom";

const MODULOS = [
  {
    grupo: "Configuración",
    items: [
      { to: "/configuracion/plan-cuentas", label: "Plan de cuentas" },
      { to: "/configuracion/terceros", label: "Terceros" },
      { to: "/configuracion/tipos-documento", label: "Tipos de documento" },
      { to: "/configuracion/resoluciones-dian", label: "Resoluciones DIAN" },
      { to: "/configuracion/centros-costo", label: "Centros de costo" },
      { to: "/configuracion/impuestos", label: "Impuestos" },
      { to: "/configuracion/unidades-medida", label: "Unidades de medida" },
      { to: "/configuracion/formas-pago", label: "Formas de pago" },
      { to: "/configuracion/usuarios-roles", label: "Usuarios y roles" },
      { to: "/configuracion/datos-empresa", label: "Datos de empresa" },
    ],
  },
  {
    grupo: "Contabilidad",
    items: [
      { to: "/contabilidad/comprobante-ajuste", label: "Comprobante de ajuste" },
      { to: "/contabilidad/notas-contables", label: "Notas contables" },
      { to: "/contabilidad/comprobante-apertura", label: "Apertura" },
      { to: "/contabilidad/comprobante-cierre", label: "Cierre" },
      { to: "/contabilidad/consulta-comprobantes", label: "Consulta comprobantes" },
      { to: "/contabilidad/auditoria-comprobantes", label: "Auditoría" },
    ],
  },
  {
    grupo: "Facturación",
    items: [
      { to: "/facturacion/factura-venta", label: "Factura de venta" },
      { to: "/facturacion/documento-equivalente-pos", label: "Documento equiv. POS" },
      { to: "/facturacion/notas-credito-debito", label: "Notas crédito/débito" },
    ],
  },
  {
    grupo: "Inventario",
    items: [
      { to: "/inventario/catalogo-productos", label: "Catálogo de productos" },
      { to: "/inventario/kardex-promedio-ponderado", label: "Kardex PP" },
      { to: "/inventario/sync-pos-online", label: "Sync POS / Online" },
    ],
  },
  {
    grupo: "Reportes",
    items: [
      { to: "/reportes/form-300-iva", label: "Form 300 IVA" },
      { to: "/reportes/form-260-simple", label: "Form 260 SIMPLE" },
      { to: "/reportes/estados-financieros", label: "Estados financieros" },
      { to: "/reportes/form-350-retenciones", label: "Form 350 (F2)" },
      { to: "/reportes/libros-oficiales", label: "Libros oficiales (F2)" },
      { to: "/reportes/exogena", label: "Exógena (F3)" },
    ],
  },
  {
    grupo: "Compras (F2)",
    items: [
      { to: "/compras/ordenes-compra", label: "Órdenes de compra" },
      { to: "/compras/recepcion-mercancia", label: "Recepción mercancía" },
      { to: "/compras/facturas-proveedor", label: "Facturas proveedor" },
      { to: "/compras/retenciones", label: "Retenciones" },
    ],
  },
  {
    grupo: "Tesorería (F2/F3)",
    items: [
      { to: "/tesoreria/caja", label: "Caja" },
      { to: "/tesoreria/bancos", label: "Bancos" },
      { to: "/tesoreria/cxc-cxp", label: "CxC / CxP" },
      { to: "/tesoreria/flujo-caja", label: "Flujo de caja" },
      { to: "/tesoreria/conciliacion-bancaria-auto", label: "Conciliación auto (F3)" },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-geifem-navy text-white overflow-y-auto">
      <div className="p-4 border-b border-white/10">
        <div className="text-xl font-bold">GEIFEM</div>
        <div className="text-[10px] uppercase tracking-wider text-geifem-gold">Contable</div>
      </div>
      <nav className="p-2 space-y-4 pb-8">
        {MODULOS.map((g) => (
          <div key={g.grupo}>
            <div className="text-[11px] uppercase tracking-wider text-slate-400 px-3 mb-1">
              {g.grupo}
            </div>
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                className={({ isActive }) =>
                  `block px-3 py-1.5 rounded text-sm ${
                    isActive
                      ? "bg-geifem-gold text-geifem-navy font-semibold"
                      : "hover:bg-white/5 text-slate-200"
                  }`
                }
              >
                {it.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
