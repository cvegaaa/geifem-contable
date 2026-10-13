"""Resoluciones de numeración de la DIAN: normalización y sincronización con el portal.

El portal (vía el proveedor tecnológico) entrega las resoluciones habilitadas; aquí se convierten al formato propio y se
crean o actualizan por (número de resolución, prefijo). La numeración ya usada nunca se retrocede.
"""
from datetime import datetime, timezone
from typing import Any

TIPOS_DOCUMENTO = {
    "01": "Factura electrónica de venta",
    "02": "Factura de exportación",
    "03": "Factura por contingencia",
    "91": "Nota crédito electrónica",
    "92": "Nota débito electrónica",
    "05": "Documento soporte en adquisiciones a no obligados",
    "07": "Documento equivalente POS electrónico",
}


def normalizar(r: dict[str, Any]) -> dict[str, Any]:
    """Resolución con los campos de la DIAN -> documento de `resoluciones_dian`."""
    def fecha(v):
        return str(v)[:10] if v else None

    return {
        "numero_resolucion": str(r.get("NumeroResolucion") or "").strip(),
        "fecha_resolucion": fecha(r.get("FechaResolucion")),
        "prefijo": str(r.get("Prefijo") or "").strip(),
        "rango_desde": int(r.get("DesdeNumero") or 0),
        "rango_hasta": int(r.get("HastaNumero") or 0),
        "fecha_inicio": fecha(r.get("FechaDesde")),
        "fecha_fin": fecha(r.get("FechaHasta")),
        "clave_tecnica": r.get("ClaveTecnica") or None,
        "tipo_documento": str(r.get("TipoDocumento") or "01"),
    }


async def aplicar(db, empresa_id: str, resoluciones: list[dict[str, Any]]) -> dict[str, int]:
    """Crea o actualiza las resoluciones recibidas; devuelve cuántas se crearon y cuántas se actualizaron."""
    ahora = datetime.now(timezone.utc)
    creadas = actualizadas = 0
    for bruta in resoluciones:
        r = normalizar(bruta)
        if not r["numero_resolucion"] or r["rango_hasta"] < r["rango_desde"]:
            continue
        filtro = {"empresa_id": empresa_id, "numero_resolucion": r["numero_resolucion"], "prefijo": r["prefijo"]}
        existente = await db.resoluciones_dian.find_one(filtro)
        datos = {**r, "origen": "dian", "estado_dian": "habilitada", "sincronizada_en": ahora}
        if existente:
            # La numeración consumida es de este sistema: la DIAN no la modifica.
            await db.resoluciones_dian.update_one({"_id": existente["_id"]}, {"$set": datos})
            actualizadas += 1
        else:
            await db.resoluciones_dian.insert_one({**filtro, **datos, "consecutivo_actual": r["rango_desde"] - 1,
                                                    "activo": True, "fecha_creacion": ahora})
            creadas += 1
    return {"creadas": creadas, "actualizadas": actualizadas}
