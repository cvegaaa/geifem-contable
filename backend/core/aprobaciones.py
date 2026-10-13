"""Aprobación de documentos: quién necesita que otro autorice lo que registra, y quién puede autorizar.

- Los comprobantes contables manejan su propio estado («por aprobar»).
- Para el resto de módulos (ventas, compras, tesorería, inventario y nómina) la petición de un usuario que requiere
  aprobación no se ejecuta: queda guardada como **solicitud** y, cuando un aprobador la autoriza, se ejecuta tal cual
  como si la hubiera hecho quien la solicitó (el documento queda a su nombre y con el aprobador registrado).
"""
import re
import secrets
from contextvars import ContextVar

# Quien aprueba la solicitud que se está ejecutando (lo lee la auditoría para dejar constancia).
from core.documentos import APROBADOR  # noqa: F401  (se re-exporta para los módulos de aprobación)

# Marca interna para que la ejecución de una solicitud aprobada no vuelva a interceptarse.
SECRETO_REPLAY = secrets.token_hex(24)
ENCABEZADO_REPLAY = "X-Ejecucion-Aprobada"

_ID = r"[0-9a-fA-F]{24}"
_RECURSOS = {
    "facturacion/facturas": ("facturacion", "Factura de venta"),
    "facturacion/documento-equivalente-pos": ("facturacion", "Documento equivalente POS"),
    "facturacion/notas-credito-debito": ("facturacion", "Nota crédito/débito"),
    "compras/ordenes-compra": ("compras", "Orden de compra"),
    "compras/recepcion-mercancia": ("compras", "Entrada de mercancía"),
    "compras/facturas-proveedor": ("compras", "Factura de proveedor"),
    "compras/devoluciones-proveedor": ("compras", "Devolución a proveedor"),
    "tesoreria/movimientos": ("tesoreria", "Movimiento de caja o banco"),
    "tesoreria/pagos": ("tesoreria", "Recibo de caja / comprobante de egreso"),
    "tesoreria/anticipos": ("tesoreria", "Anticipo"),
    "tesoreria/transferencias": ("tesoreria", "Transferencia entre cuentas"),
    "inventario/kardex/movimientos": ("inventario", "Ajuste de inventario"),
    "nomina/periodos": ("nomina", "Liquidación de nómina"),
    "nomina/pagos": ("nomina", "Pago de nómina"),
    "nomina/pagos-obligaciones": ("nomina", "Pago de prestaciones o aportes"),
    "nomina/liquidaciones-finales": ("nomina", "Liquidación de contrato"),
}
_ALT = "|".join(re.escape(r) for r in sorted(_RECURSOS, key=len, reverse=True))
_CREAR = re.compile(rf"^/api/({_ALT})(/multiple)?$")
_EDITAR = re.compile(rf"^/api/({_ALT})/{_ID}$")
_ANULAR = re.compile(rf"^/api/({_ALT})/{_ID}/anular$")
_APLICAR = re.compile(rf"^/api/(tesoreria/anticipos)/{_ID}/aplicar$")
_CONTABILIZAR = re.compile(rf"^/api/(compras)/facturas-recibidas/{_ID}/contabilizar$")


def clasificar(metodo: str, ruta: str) -> dict | None:
    """Si la petición crea, edita o anula un documento cubierto: módulo, acción de permiso y descripción."""
    if metodo == "POST":
        if m := _CREAR.match(ruta):
            modulo, nombre = _RECURSOS[m.group(1)]
            return {"modulo": modulo, "permiso": "crear", "descripcion": f"Crear: {nombre}" + (" (varias facturas)" if m.group(2) else "")}
        if m := _ANULAR.match(ruta):
            modulo, nombre = _RECURSOS[m.group(1)]
            return {"modulo": modulo, "permiso": "inactivar", "descripcion": f"Anular: {nombre}"}
        if _APLICAR.match(ruta):
            return {"modulo": "tesoreria", "permiso": "crear", "descripcion": "Aplicar anticipo a una factura"}
        if _CONTABILIZAR.match(ruta):
            return {"modulo": "compras", "permiso": "crear", "descripcion": "Contabilizar factura electrónica recibida"}
    if metodo == "PUT" and (m := _EDITAR.match(ruta)):
        modulo, nombre = _RECURSOS[m.group(1)]
        return {"modulo": modulo, "permiso": "editar", "descripcion": f"Editar: {nombre}"}
    return None


def requiere_aprobacion(usuario: dict) -> bool:
    """Usuarios cuyos documentos quedan «por aprobar» hasta que un aprobador los autorice."""
    marca = usuario.get("requiere_aprobacion")
    if marca is not None:
        return bool(marca)
    if "rol_requiere_aprobacion" in usuario:
        return bool(usuario["rol_requiere_aprobacion"])
    return usuario.get("rol") == "auxiliar"


def puede_aprobar(usuario: dict, modulo: str = "contabilidad") -> bool:
    """Quien tiene el permiso «aprobar» en el módulo (el administrador lo tiene en todos)."""
    return "aprobar" in (usuario.get("permisos") or {}).get(modulo, [])


__all__ = ["APROBADOR", "ContextVar", "SECRETO_REPLAY", "ENCABEZADO_REPLAY", "clasificar", "puede_aprobar", "requiere_aprobacion"]
