"""Permisos por módulo. Fase 1: permisos base por rol; en fases posteriores
la UI permitirá personalizar por usuario dentro del rol."""

MODULOS = [
    "configuracion",
    "contabilidad",
    "facturacion",
    "inventario",
    "reportes",
    "compras",
    "tesoreria",
    "nomina",
]

# "aprobar": autoriza los documentos de quienes requieren aprobación (hoy, comprobantes contables).
ACCIONES = ["leer", "crear", "editar", "inactivar", "aprobar"]

PERMISOS_POR_ROL: dict[str, dict[str, list[str]]] = {
    "admin": {m: ACCIONES.copy() for m in MODULOS},
    "contador": {
        "configuracion": ["leer", "crear", "editar", "inactivar"],
        "contabilidad": ACCIONES.copy(),
        "facturacion": ["leer", "aprobar"],
        "inventario": ["leer", "aprobar"],
        "reportes": ["leer", "crear"],
        "compras": ["leer", "aprobar"],
        "tesoreria": ["leer", "aprobar"],
        "nomina": ACCIONES.copy(),
    },
    # Auxiliar contable: registra comprobantes, pero un administrador o contador debe aprobarlos.
    "auxiliar": {
        "configuracion": ["leer"],
        "contabilidad": ["leer", "crear", "editar"],
        "facturacion": ["leer"],
        "inventario": ["leer"],
        "reportes": ["leer"],
        "compras": ["leer"],
        "tesoreria": ["leer"],
        "nomina": [],
    },
    "vendedor": {
        "configuracion": ["leer"],
        "contabilidad": ["leer"],
        "facturacion": ["leer", "crear", "editar"],
        "inventario": ["leer"],
        "reportes": ["leer"],
        "compras": [],
        "tesoreria": [],
        "nomina": [],
    },
}


def permisos_efectivos(rol: str, permisos: dict | None) -> dict[str, list[str]]:
    """Permisos guardados del usuario; los módulos nuevos que aún no tiene toman la plantilla de su rol."""
    return {**permisos_base(rol), **(permisos or {})}


def permisos_base(rol: str) -> dict[str, list[str]]:
    return {m: acc.copy() for m, acc in PERMISOS_POR_ROL.get(rol, {}).items()}
