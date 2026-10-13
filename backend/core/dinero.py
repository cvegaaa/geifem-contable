"""Dinero exacto.

Los valores monetarios viajan como números (JSON y Mongo) pero **todo cálculo se redondea con
aritmética decimal y redondeo contable (mitad hacia arriba)**, no con el redondeo binario de
`float`/`round`, que da 2,67 para 2,675. El cuadre de los asientos se compara en centavos enteros.
"""
from decimal import ROUND_HALF_UP, Decimal


def _d(valor) -> Decimal:
    # `str(float)` da la representación más corta (0.1 -> '0.1'), evitando el ruido binario.
    return Decimal(str(valor))


def redondear(valor, decimales: int = 2) -> float:
    """Redondeo contable (mitad hacia arriba). `decimales` negativo redondea a decenas, centenas, etc."""
    return float(_d(valor).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP))


def centavos(valor) -> int:
    """Valor en centavos enteros, para comparar y sumar sin error de punto flotante."""
    return int(_d(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
