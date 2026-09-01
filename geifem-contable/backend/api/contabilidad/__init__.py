"""Routers FASE 1 de Contabilidad: comprobantes + consulta + auditoría."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth.dependencies import get_current_user, get_empresa_activa, require_permiso
from db import get_db

router = APIRouter(prefix="/api/contabilidad", tags=["contabilidad"])


class LineaComprobante(BaseModel):
    cuenta_puc_id: str
    debito: float = 0
    credito: float = 0
    descripcion: str | None = None


class ComprobanteCrear(BaseModel):
    tipo: str  # ajuste | nota | apertura | cierre
    fecha: str
    tercero_id: str | None = None
    lineas: list[LineaComprobante] = Field(min_length=1)
    descripcion: str | None = None
    estado: str = "borrador"  # borrador | contabilizado


async def _audit(comprobante_id: str, usuario_id: str, accion: str, detalle: dict | None = None):
    db = get_db()
    await db.auditoria_comprobantes.insert_one(
        {
            "comprobante_id": comprobante_id,
            "usuario_id": usuario_id,
            "accion": accion,
            "fecha_hora": datetime.now(timezone.utc),
            "detalle": detalle or {},
        }
    )


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.post("/comprobantes", status_code=201)
async def crear_comprobante(
    payload: ComprobanteCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "crear")),
):
    total_deb = sum(l.debito for l in payload.lineas)
    total_cre = sum(l.credito for l in payload.lineas)
    if round(total_deb, 2) != round(total_cre, 2):
        raise HTTPException(422, "Comprobante descuadrado (débitos ≠ créditos)")

    db = get_db()
    seq = await db.comprobantes_contables.count_documents(
        {"empresa_id": empresa_id, "tipo": payload.tipo}
    )
    doc = payload.model_dump()
    doc.update(
        {
            "empresa_id": empresa_id,
            "consecutivo": seq + 1,
            "creado_por": usuario["id"],
            "fecha_creacion": datetime.now(timezone.utc),
        }
    )
    result = await db.comprobantes_contables.insert_one(doc)
    await _audit(str(result.inserted_id), usuario["id"], "creado")
    return _serialize(await db.comprobantes_contables.find_one({"_id": result.inserted_id}))


@router.get("/comprobantes")
async def consultar_comprobantes(
    tipo: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    db = get_db()
    filtro: dict = {"empresa_id": empresa_id}
    if tipo:
        filtro["tipo"] = tipo
    if desde or hasta:
        filtro["fecha"] = {}
        if desde:
            filtro["fecha"]["$gte"] = desde
        if hasta:
            filtro["fecha"]["$lte"] = hasta
    return [_serialize(d) async for d in db.comprobantes_contables.find(filtro).sort("fecha", -1)]


@router.get("/comprobantes/{cid}")
async def obtener_comprobante(
    cid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    db = get_db()
    doc = await db.comprobantes_contables.find_one({"_id": ObjectId(cid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "No encontrado")
    return _serialize(doc)


@router.put("/comprobantes/{cid}")
async def editar_comprobante(
    cid: str,
    payload: ComprobanteCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "editar")),
):
    db = get_db()
    oid = ObjectId(cid)
    existente = await db.comprobantes_contables.find_one({"_id": oid, "empresa_id": empresa_id})
    if not existente:
        raise HTTPException(404, "No encontrado")
    if existente.get("estado") == "contabilizado":
        raise HTTPException(409, "No se puede editar un comprobante contabilizado")
    data = payload.model_dump()
    await db.comprobantes_contables.update_one({"_id": oid}, {"$set": data})
    await _audit(cid, usuario["id"], "editado", detalle={"campos": list(data.keys())})
    return _serialize(await db.comprobantes_contables.find_one({"_id": oid}))


@router.get("/auditoria")
async def listar_auditoria(
    comprobante_id: str | None = Query(None),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    db = get_db()
    filtro = {"comprobante_id": comprobante_id} if comprobante_id else {}
    return [_serialize(d) async for d in db.auditoria_comprobantes.find(filtro).sort("fecha_hora", -1)]
