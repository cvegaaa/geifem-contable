"""Dígito de verificación del NIT colombiano (módulo 11, pesos DIAN)."""
import re

_PESOS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def limpiar(numero: str | None) -> str:
    return re.sub(r"\D", "", numero or "")


def digito_verificacion(numero: str | None) -> str | None:
    """DV de un NIT; None si no es numérico o excede 15 dígitos."""
    n = limpiar(numero)
    if not n or len(n) > len(_PESOS):
        return None
    total = sum(int(d) * p for d, p in zip(reversed(n), _PESOS))
    r = total % 11
    return str(r if r < 2 else 11 - r)
