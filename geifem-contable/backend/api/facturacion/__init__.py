"""Facturación FASE 1: CRUD base de facturas + envío al PT (stub).

La lógica DIAN real (envío + CUFE + XML) se conecta con el ClientePT en
fases posteriores. Fase 1 permite registrar la factura y generar el asiento
contable espejo mínimo.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from core.auth.dependencies import get_empresa_activa, require_permiso
from core.dian.cliente_pt import get_cliente_pt
from db import get_db

router = APIRouter(prefix="/api/facturacion", tags=["facturacion"])


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/facturas")
async def listar_facturas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.facturas.find({"empresa_id": empresa_id}).sort("fecha", -1)]


@router.post("/facturas", status_code=201)
async def crear_factura(
    payload: dict,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()
    payload.update(
        {
            "empresa_id": empresa_id,
            "estado_dian": "borrador",
            "fecha_creacion": datetime.now(timezone.utc),
        }
    )
    result = await db.facturas.insert_one(payload)
    return _serialize(await db.facturas.find_one({"_id": result.inserted_id}))


@router.post("/facturas/{fid}/enviar-dian")
async def enviar_dian(
    fid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "editar")),
):
    """Stub Fase 1: llama al ClientePT (no configurado). Deja el contrato listo."""
    db = get_db()
    factura = await db.facturas.find_one({"_id": ObjectId(fid), "empresa_id": empresa_id})
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    pt = get_cliente_pt()
    try:
        resultado = await pt.enviar_factura(empresa_id, factura)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))
    await db.facturas.update_one({"_id": ObjectId(fid)}, {"$set": resultado})
    return {"ok": True, **resultado}


# Sub-recursos: documento-equivalente-pos y notas-credito-debito (stubs Fase 1)
@router.get("/documento-equivalente-pos")
async def listar_pos(empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("facturacion", "leer"))):
    db = get_db()
    return [_serialize(d) async for d in db.documentos_pos.find({"empresa_id": empresa_id})]


@router.get("/notas-credito-debito")
async def listar_notas(empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("facturacion", "leer"))):
    db = get_db()
    return [_serialize(d) async for d in db.notas_credito_debito.find({"empresa_id": empresa_id})]
