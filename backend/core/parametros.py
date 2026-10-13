"""Parametrización contable por empresa.

Define qué cuenta del PUC usa cada asiento automático. La empresa puede
cambiar cualquiera desde Configuración › Parámetros contables; además:

- cada producto puede tener sus propias cuentas de inventario, ingreso y
  costo (si no, usa las de la empresa);
- cada caja y cada cuenta bancaria tiene su propia cuenta contable.
"""
from fastapi import HTTPException
from pymongo.asynchronous.client_session import AsyncClientSession

from db import get_db

# clave -> (grupo, descripción, código por defecto)
PARAMETROS: dict[str, tuple[str, str, str]] = {
    "clientes": ("Ventas", "Cuentas por cobrar a clientes", "1305"),
    "ingresos": ("Ventas", "Ingresos por ventas (si el producto no tiene otra)", "4135"),
    "devoluciones": ("Ventas", "Devoluciones en ventas (notas crédito)", "4175"),
    "iva_generado": ("Ventas", "IVA generado en ventas", "2408"),
    "costo_venta": ("Ventas", "Costo de ventas (si el producto no tiene otra)", "6135"),
    "inventario": ("Inventario", "Inventario de mercancía (si el producto no tiene otra)", "1435"),
    "inventario_por_facturar": ("Inventario", "Mercancía recibida pendiente de factura del proveedor", "2335"),
    "ajuste_faltante": ("Inventario", "Pérdida por faltantes de inventario", "5195"),
    "ajuste_sobrante": ("Inventario", "Ingreso por sobrantes de inventario", "4295"),
    "proveedores": ("Compras", "Cuentas por pagar a proveedores", "2205"),
    "iva_descontable": ("Compras", "IVA descontable en compras", "2408"),
    "gasto_compras": ("Compras", "Gasto por defecto en compras que no son mercancía", "5195"),
    "retefuente": ("Compras", "Retención en la fuente practicada", "2365"),
    "reteiva": ("Compras", "ReteIVA practicada", "2367"),
    "reteica": ("Compras", "ReteICA practicada", "2368"),
    "retefuente_favor": ("Impuestos", "Retención en la fuente que te practican (a favor)", "1355"),
    "reteiva_favor": ("Impuestos", "ReteIVA que te practican (a favor)", "1355"),
    "reteica_favor": ("Impuestos", "ReteICA que te practican (a favor)", "1355"),
    "autorretencion_anticipo": ("Impuestos", "Autorretención de renta: anticipo (débito)", "1355"),
    "autorretencion_pasivo": ("Impuestos", "Autorretención de renta por pagar (crédito)", "2365"),
    "saldos_iniciales": ("Tesorería", "Contrapartida de los saldos iniciales de caja y bancos", "3105"),
    "nomina_gasto_salarios": ("Nómina", "Gasto de sueldos, vacaciones, comisiones y bonificaciones", "5105"),
    "nomina_gasto_horas_extra": ("Nómina", "Gasto de horas extra y recargos", "5105"),
    "nomina_gasto_aux_transporte": ("Nómina", "Gasto de auxilio de transporte", "5105"),
    "nomina_gasto_seguridad_social": ("Nómina", "Gasto de seguridad social del empleador (salud, pensión, ARL)", "5105"),
    "nomina_gasto_parafiscales": ("Nómina", "Gasto de parafiscales (caja, SENA, ICBF)", "5105"),
    "nomina_gasto_prestaciones": ("Nómina", "Gasto de prestaciones sociales (provisión)", "5105"),
    "nomina_gasto_indemnizacion": ("Nómina", "Gasto de indemnizaciones", "5105"),
    "nomina_salarios_por_pagar": ("Nómina", "Salarios por pagar (neto a empleados)", "2505"),
    "nomina_aportes_empleado": ("Nómina", "Aportes del empleado por pagar (salud, pensión, solidaridad)", "2370"),
    "nomina_aportes_empleador": ("Nómina", "Aportes del empleador por pagar (seguridad social y parafiscales)", "2370"),
    "nomina_retefuente": ("Nómina", "Retención en la fuente por pagos laborales", "2365"),
    "nomina_otros_descuentos": ("Nómina", "Embargos, libranzas y otros descuentos por pagar", "2380"),
    "nomina_prestamos_empleados": ("Nómina", "Préstamos a empleados (cuentas por cobrar)", "1365"),
    "nomina_eps_por_cobrar": ("Nómina", "Incapacidades y licencias por cobrar a EPS/ARL", "1380"),
    "nomina_cesantias": ("Nómina", "Cesantías consolidadas", "2510"),
    "nomina_intereses": ("Nómina", "Intereses sobre cesantías", "2515"),
    "nomina_prima": ("Nómina", "Prima de servicios", "2520"),
    "nomina_vacaciones": ("Nómina", "Vacaciones consolidadas", "2525"),
    "caja": ("Tesorería", "Caja (si la caja no tiene cuenta propia)", "1105"),
    "bancos": ("Tesorería", "Bancos (si la cuenta bancaria no tiene cuenta propia)", "1110"),
}

# Cuentas propias que admite un producto: campo del producto -> parámetro de respaldo.
CUENTAS_PRODUCTO = {
    "cuenta_inventario": "inventario",
    "cuenta_ingreso": "ingresos",
    "cuenta_costo": "costo_venta",
}


def por_defecto() -> dict[str, str]:
    return {clave: codigo for clave, (_, _, codigo) in PARAMETROS.items()}


async def obtener(empresa_id: str, s: AsyncClientSession | None = None) -> dict[str, str]:
    """Parámetros vigentes: los guardados por la empresa sobre los valores por defecto."""
    doc = await get_db().parametros_contables.find_one({"empresa_id": empresa_id}, session=s)
    guardados = {k: v for k, v in (doc or {}).get("cuentas", {}).items() if k in PARAMETROS and v}
    return {**por_defecto(), **guardados}


async def validar_codigos(empresa_id: str, codigos: dict[str, str | None]) -> None:
    """Cada código indicado debe existir en el plan de la empresa y recibir movimientos."""
    db = get_db()
    for campo, codigo in codigos.items():
        if not codigo:
            continue
        cuenta = await db.plan_cuentas.find_one(
            {"empresa_id": empresa_id, "codigo": codigo, "activo": {"$ne": False}}
        )
        if not cuenta:
            raise HTTPException(422, f"{campo}: la cuenta {codigo} no existe en el plan de cuentas")
        if cuenta.get("acepta_movimientos") is False:
            raise HTTPException(422, f"{campo}: la cuenta {codigo} es de agrupación y no recibe movimientos")


def cuenta_producto(producto: dict | None, campo: str, params: dict[str, str]) -> str:
    """Cuenta del producto si la tiene configurada; si no, la de la empresa."""
    return (producto or {}).get(campo) or params[CUENTAS_PRODUCTO[campo]]
