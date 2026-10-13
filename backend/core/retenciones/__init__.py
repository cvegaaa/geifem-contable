"""Valor de la UVT por año (base de las cuantías mínimas de retención).

Verificar cada año contra la resolución de la DIAN.
"""

UVT_POR_ANIO = {
    2023: 42412,
    2024: 47065,
    2025: 49799,
    2026: 52374,
}
UVT_DEFECTO = UVT_POR_ANIO[max(UVT_POR_ANIO)]


def valor_uvt(anio: int | None = None) -> int:
    if anio and anio in UVT_POR_ANIO:
        return UVT_POR_ANIO[anio]
    return UVT_DEFECTO


def anio_de(fecha: str | None) -> int | None:
    try:
        return int(str(fecha)[:4])
    except (TypeError, ValueError):
        return None
