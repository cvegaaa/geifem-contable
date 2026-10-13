"""Aprobación de documentos: quién necesita que otro autorice lo que registra, y quién puede autorizar.

Hoy aplica a los comprobantes contables; el mismo criterio sirve para el resto de documentos.
"""


def requiere_aprobacion(usuario: dict) -> bool:
    """Usuarios cuyos documentos quedan «por aprobar» hasta que un aprobador los autorice."""
    marca = usuario.get("requiere_aprobacion")
    if marca is not None:
        return bool(marca)
    return usuario.get("rol") == "auxiliar"


def puede_aprobar(usuario: dict, modulo: str = "contabilidad") -> bool:
    if usuario.get("rol") in ("admin", "contador"):
        return True
    return "aprobar" in (usuario.get("permisos") or {}).get(modulo, [])
