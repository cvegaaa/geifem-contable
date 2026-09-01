"""Motor de retenciones (ReteFuente / ReteICA / ReteIVA) — Fase 2.

Calcula las retenciones de un documento a partir de:
- los conceptos parametrizados por empresa (colección `conceptos_retencion`), o
- tarifas manuales indicadas en el documento.

Reglas aplicadas:
- Base mínima en UVT por concepto: si la base gravable es inferior a
  `base_uvt * valor_uvt`, no se practica la retención.
- ReteFuente y ReteICA se calculan sobre el subtotal (base gravable).
  ReteICA se expresa en x1000 (tarifa municipal por mil).
- ReteIVA se calcula sobre el IVA facturado.

El valor de la UVT debe actualizarse cada año (decreto DIAN); se puede
sobreescribir por empresa en `configuracion/impuestos` (campo `valor_uvt`).
"""

# UVT por año gravable (verificar decreto anual de la DIAN).
UVT_POR_ANIO = {
    2023: 42412,
    2024: 47065,
    2025: 49799,
    2026: 52374,
}
UVT_DEFECTO = UVT_POR_ANIO[max(UVT_POR_ANIO)]

TIPOS = ("retefuente", "reteica", "reteiva")


def valor_uvt(anio: int | None = None) -> int:
    if anio and anio in UVT_POR_ANIO:
        return UVT_POR_ANIO[anio]
    return UVT_DEFECTO


def _anio(fecha: str | None) -> int | None:
    try:
        return int(str(fecha)[:4])
    except (TypeError, ValueError):
        return None


def _tarifa_efectiva(tipo: str, tarifa: float) -> float:
    """ReteICA se parametriza por mil; el resto en porcentaje."""
    return tarifa / 1000 if tipo == "reteica" else tarifa / 100


def calcular_retenciones(
    subtotal: float,
    iva: float,
    conceptos: list[dict] | None = None,
    tarifas: dict[str, float] | None = None,
    fecha: str | None = None,
    uvt: int | None = None,
) -> dict:
    """Devuelve {retenciones, total, detalle} para un documento.

    `conceptos`: documentos de `conceptos_retencion` seleccionados
    ({nombre, tipo, tarifa, base_uvt}). Tienen prioridad sobre `tarifas`.
    `tarifas`: {"retefuente": %, "reteica": x1000, "reteiva": %} manual.
    """
    uvt = uvt or valor_uvt(_anio(fecha))
    retenciones = {t: 0.0 for t in TIPOS}
    detalle: list[dict] = []

    def aplicar(tipo: str, tarifa: float, base_uvt: float, nombre: str):
        tipo = (tipo or "").lower()
        if tipo not in TIPOS or not tarifa:
            return
        base = iva if tipo == "reteiva" else subtotal
        minimo = round((base_uvt or 0) * uvt, 2)
        if base < minimo:
            detalle.append({
                "concepto": nombre, "tipo": tipo, "tarifa": tarifa, "base": round(base, 2),
                "base_minima": minimo, "valor": 0.0, "aplica": False,
                "motivo": f"Base inferior a la cuantía mínima ({base_uvt} UVT)",
            })
            return
        valor = round(base * _tarifa_efectiva(tipo, tarifa), 2)
        retenciones[tipo] = round(retenciones[tipo] + valor, 2)
        detalle.append({
            "concepto": nombre, "tipo": tipo, "tarifa": tarifa, "base": round(base, 2),
            "base_minima": minimo, "valor": valor, "aplica": True, "motivo": None,
        })

    for c in conceptos or []:
        aplicar(c.get("tipo", ""), float(c.get("tarifa", 0) or 0),
                float(c.get("base_uvt", 0) or 0), c.get("nombre", "Concepto"))

    for tipo, tarifa in (tarifas or {}).items():
        if tarifa:
            aplicar(tipo, float(tarifa), 0, f"Tarifa manual {tipo}")

    return {
        "retenciones": retenciones,
        "total": round(sum(retenciones.values()), 2),
        "detalle": detalle,
        "uvt": uvt,
    }
