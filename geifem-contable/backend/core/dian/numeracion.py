"""Gestión de rangos de numeración DIAN por empresa.

Referencia a la colección `resoluciones_dian` administrada desde
`configuracion/resoluciones-dian`.
"""
from datetime import date

from fastapi import HTTPException

from db import get_db


async def obtener_siguiente_consecutivo(
    empresa_id: str, tipo_documento_id: str, hoy: date | None = None
) -> tuple[str, int]:
    """Devuelve (prefijo, siguiente_numero) para una resolución vigente."""
    hoy = hoy or date.today()
    db = get_db()
    resolucion = await db.resoluciones_dian.find_one(
        {
            "empresa_id": empresa_id,
            "tipo_documento_id": tipo_documento_id,
            "fecha_inicio": {"$lte": hoy.isoformat()},
            "fecha_fin": {"$gte": hoy.isoformat()},
            "activo": True,
        }
    )
    if not resolucion:
        raise HTTPException(status_code=409, detail="No hay resolución DIAN vigente")
    actual = resolucion.get("consecutivo_actual", resolucion["rango_desde"] - 1)
    siguiente = actual + 1
    if siguiente > resolucion["rango_hasta"]:
        raise HTTPException(status_code=409, detail="Rango DIAN agotado")
    await db.resoluciones_dian.update_one(
        {"_id": resolucion["_id"]}, {"$set": {"consecutivo_actual": siguiente}}
    )
    return resolucion["prefijo"], siguiente
