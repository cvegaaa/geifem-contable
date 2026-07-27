"""Fábrica de routers CRUD genéricos multi-tenant.

Cada recurso vive scoped por `empresa_id` (empresa activa del usuario). El
borrado es lógico: `activo=False` en lugar de eliminar el documento.
"""
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def crud_router(
    *,
    prefix: str,
    coleccion: str,
    modulo_permiso: str,
    tags: list[str] | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=tags or [prefix.strip("/")])

    @router.get("")
    async def listar(
        incluir_inactivos: bool = Query(False),
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso(modulo_permiso, "leer")),
    ) -> list[dict[str, Any]]:
        db = get_db()
        filtro: dict = {"empresa_id": empresa_id}
        if not incluir_inactivos:
            filtro["activo"] = {"$ne": False}
        cursor = db[coleccion].find(filtro)
        return [_serialize(d) async for d in cursor]

    @router.post("", status_code=201)
    async def crear(
        payload: dict,
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso(modulo_permiso, "crear")),
    ) -> dict:
        db = get_db()
        payload["empresa_id"] = empresa_id
        payload.setdefault("activo", True)
        payload["fecha_creacion"] = datetime.now(timezone.utc)
        result = await db[coleccion].insert_one(payload)
        doc = await db[coleccion].find_one({"_id": result.inserted_id})
        return _serialize(doc)

    @router.get("/{item_id}")
    async def obtener(
        item_id: str,
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso(modulo_permiso, "leer")),
    ) -> dict:
        db = get_db()
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(400, "id inválido")
        doc = await db[coleccion].find_one({"_id": oid, "empresa_id": empresa_id})
        if not doc:
            raise HTTPException(404, "No encontrado")
        return _serialize(doc)

    @router.put("/{item_id}")
    async def editar(
        item_id: str,
        payload: dict,
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso(modulo_permiso, "editar")),
    ) -> dict:
        db = get_db()
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(400, "id inválido")
        payload.pop("empresa_id", None)
        payload.pop("id", None)
        payload["fecha_actualizacion"] = datetime.now(timezone.utc)
        result = await db[coleccion].update_one(
            {"_id": oid, "empresa_id": empresa_id}, {"$set": payload}
        )
        if not result.matched_count:
            raise HTTPException(404, "No encontrado")
        doc = await db[coleccion].find_one({"_id": oid})
        return _serialize(doc)

    @router.post("/{item_id}/inactivar")
    async def inactivar(
        item_id: str,
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso(modulo_permiso, "inactivar")),
    ) -> dict:
        db = get_db()
        try:
            oid = ObjectId(item_id)
        except Exception:
            raise HTTPException(400, "id inválido")
        result = await db[coleccion].update_one(
            {"_id": oid, "empresa_id": empresa_id}, {"$set": {"activo": False}}
        )
        if not result.matched_count:
            raise HTTPException(404, "No encontrado")
        return {"ok": True, "id": item_id}

    return router
