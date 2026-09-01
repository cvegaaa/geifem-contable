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
]

ACCIONES = ["leer", "crear", "editar", "inactivar"]

PERMISOS_POR_ROL: dict[str, dict[str, list[str]]] = {
    "admin": {m: ACCIONES.copy() for m in MODULOS},
    "contador": {
        "configuracion": ["leer", "crear", "editar", "inactivar"],
        "contabilidad": ACCIONES.copy(),
        "facturacion": ["leer"],
        "inventario": ["leer"],
        "reportes": ["leer", "crear"],
        "compras": ["leer"],
        "tesoreria": ["leer"],
    },
    "vendedor": {
        "configuracion": ["leer"],
        "contabilidad": ["leer"],
        "facturacion": ["leer", "crear", "editar"],
        "inventario": ["leer"],
        "reportes": ["leer"],
        "compras": [],
        "tesoreria": [],
    },
}


def permisos_base(rol: str) -> dict[str, list[str]]:
    return {m: acc.copy() for m, acc in PERMISOS_POR_ROL.get(rol, {}).items()}
