"""Webhooks del Proveedor Tecnológico: acuse, aceptación, rechazo.

FASE 1: contrato del endpoint. La firma / verificación real se implementa
cuando se configure el PT.
"""
from fastapi import APIRouter, Request

from db import get_db

router = APIRouter(prefix="/api/dian/webhooks", tags=["dian-webhooks"])


@router.post("/estado")
async def recibir_estado(request: Request):
    """Recibe callbacks del PT con el estado de una factura."""
    payload = await request.json()
    cufe = payload.get("cufe")
    estado = payload.get("estado")  # acuse | aceptado | rechazado
    if not cufe or not estado:
        return {"ok": False, "detail": "payload incompleto"}
    db = get_db()
    await db.facturas.update_one(
        {"cufe": cufe}, {"$set": {"estado_dian": estado, "webhook_payload": payload}}
    )
    return {"ok": True}
