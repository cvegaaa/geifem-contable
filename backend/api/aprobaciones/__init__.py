"""Solicitudes de aprobación de documentos de ventas, compras, tesorería, inventario y nómina.

Cuando un usuario que requiere aprobación intenta crear, editar o anular uno de esos documentos, la petición se guarda
como solicitud en lugar de ejecutarse. Un aprobador (permiso «aprobar» del módulo) la revisa y, si la autoriza, se
ejecuta tal cual como si la hubiera hecho el solicitante: el documento queda a su nombre y la auditoría registra
quién lo aprobó. Los comprobantes contables tienen su propio estado «por aprobar» y se listan aquí junto con las solicitudes.
"""
import json
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.aprobaciones import (
    APROBADOR,
    ENCABEZADO_REPLAY,
    SECRETO_REPLAY,
    clasificar,
    puede_aprobar,
    requiere_aprobacion,
)
from core.auth.dependencies import get_current_user, get_empresa_activa
from core.auth.jwt_utils import create_access_token
from core.auth.permissions import MODULOS
from core.documentos import auditar, oid
from db import get_db

router = APIRouter(prefix="/api/aprobaciones", tags=["aprobaciones"])

ENTRADAS_RESUMEN = ("fecha", "valor", "total", "motivo", "numero_factura", "concepto", "observaciones", "tipo", "documento_tipo")


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _resumen(datos) -> dict:
    if not isinstance(datos, dict):
        return {}
    r = {k: datos[k] for k in ENTRADAS_RESUMEN if k in datos and not isinstance(datos[k], (dict, list))}
    if isinstance(datos.get("items"), list):
        r["líneas"] = len(datos["items"])
        total = sum(float(i.get("cantidad", 0)) * float(i.get("precio_unitario", i.get("costo_unitario", 0)) or 0)
                    for i in datos["items"] if isinstance(i, dict))
        if total:
            r["subtotal_estimado"] = round(total, 2)
    if isinstance(datos.get("aplicaciones"), list):
        r["facturas"] = len(datos["aplicaciones"])
        r["valor"] = round(sum(float(a.get("valor", 0)) for a in datos["aplicaciones"] if isinstance(a, dict)), 2)
    return r


async def interceptar(request: Request, call_next):
    """Middleware: la petición de un usuario que requiere aprobación se guarda como solicitud en vez de ejecutarse."""
    clase = clasificar(request.method, request.url.path)
    if not clase or request.headers.get(ENCABEZADO_REPLAY) == SECRETO_REPLAY:
        return await call_next(request)
    try:
        user = await get_current_user(request)
    except HTTPException:
        return await call_next(request)          # sin sesión válida responde el flujo normal (401)
    empresa_id = request.headers.get("X-Empresa-Id")
    if not requiere_aprobacion(user) or empresa_id not in user.get("empresa_ids", []):
        return await call_next(request)
    if clase["permiso"] not in user["permisos"].get(clase["modulo"], []):
        return JSONResponse({"detail": f"Permiso requerido: {clase['modulo']}:{clase['permiso']}"}, status_code=403)
    cuerpo = await request.body()
    try:
        datos = json.loads(cuerpo) if cuerpo else None
    except ValueError:
        return JSONResponse({"detail": "El cuerpo de la petición no es JSON válido"}, status_code=422)
    res = await get_db().solicitudes_aprobacion.insert_one({
        "empresa_id": empresa_id, "usuario_id": user["id"], "modulo": clase["modulo"], "descripcion": clase["descripcion"],
        "metodo": request.method, "ruta": request.url.path, "cuerpo": json.dumps(datos, ensure_ascii=False),
        "resumen": _resumen(datos), "estado": "pendiente", "creado_en": _ahora()})
    return JSONResponse(status_code=202, content={
        "por_aprobar": True, "solicitud_id": str(res.inserted_id),
        "detail": f"Pendiente de aprobación: «{clase['descripcion']}» quedó enviado a un aprobador y se registrará cuando lo autorice.",
    })


def _modulos_aprobables(user: dict) -> list[str]:
    return [m for m in MODULOS if puede_aprobar(user, m)]


async def _nombres(ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {str(u["_id"]): u.get("nombre", "") async for u in get_db().usuarios.find({"_id": {"$in": [oid(i) for i in ids]}}, {"nombre": 1})}


def _item(s: dict, user: dict, nombres: dict[str, str]) -> dict:
    return {
        "id": str(s["_id"]), "tipo": "solicitud", "descripcion": s["descripcion"], "modulo": s["modulo"],
        "usuario_id": s["usuario_id"], "usuario_nombre": nombres.get(s["usuario_id"], ""), "creado_en": s["creado_en"],
        "estado": s["estado"], "resumen": s.get("resumen", {}), "motivo_rechazo": s.get("motivo_rechazo"),
        "ultimo_error": s.get("ultimo_error"), "resultado": s.get("resultado"),
        "aprobado_por": nombres.get(s.get("aprobado_por", ""), ""), "propio": s["usuario_id"] == user["id"],
        "puede_resolver": s["estado"] == "pendiente" and puede_aprobar(user, s["modulo"]) and s["usuario_id"] != user["id"],
    }


@router.get("")
async def listar(
    estado: str = "pendiente",
    empresa_id: str = Depends(get_empresa_activa),
    user: dict = Depends(get_current_user),
):
    """Quien aprueba ve las solicitudes de los módulos que aprueba; los demás, solo las suyas."""
    db = get_db()
    aprobables = _modulos_aprobables(user)
    filtro: dict = {"empresa_id": empresa_id, "$or": [{"usuario_id": user["id"]}, {"modulo": {"$in": aprobables}}]}
    if estado != "todas":
        filtro["estado"] = estado
    solicitudes = [s async for s in db.solicitudes_aprobacion.find(filtro).sort("creado_en", -1).limit(300)]
    comprobantes = []
    if estado in ("pendiente", "todas"):
        cf = {"empresa_id": empresa_id, "estado": "por_aprobar"}
        if "contabilidad" not in aprobables:
            cf["creado_por"] = user["id"]
        comprobantes = [c async for c in db.comprobantes_contables.find(cf).sort("fecha", -1).limit(300)]
    nombres = await _nombres({s["usuario_id"] for s in solicitudes} | {s.get("aprobado_por") for s in solicitudes}
                             | {c.get("creado_por") for c in comprobantes})
    items = [_item(s, user, nombres) for s in solicitudes]
    for c in comprobantes:
        items.append({
            "id": str(c["_id"]), "tipo": "comprobante", "descripcion": f"Comprobante contable {c['numero']}", "modulo": "contabilidad",
            "usuario_id": c.get("creado_por"), "usuario_nombre": nombres.get(c.get("creado_por", ""), ""),
            "creado_en": c.get("fecha_creacion"), "estado": "pendiente",
            "resumen": {"fecha": c["fecha"], "valor": round(sum(float(l.get("debito", 0)) for l in c.get("lineas", [])), 2),
                        "descripcion": c.get("descripcion")},
            "propio": c.get("creado_por") == user["id"],
            "puede_resolver": "contabilidad" in aprobables and not (c.get("creado_por") == user["id"] and requiere_aprobacion(user)),
        })
    items.sort(key=lambda i: i["creado_en"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


@router.get("/contar")
async def contar(empresa_id: str = Depends(get_empresa_activa), user: dict = Depends(get_current_user)):
    """Cuántas solicitudes esperan al usuario como aprobador (para el aviso del menú)."""
    db = get_db()
    aprobables = _modulos_aprobables(user)
    n = await db.solicitudes_aprobacion.count_documents(
        {"empresa_id": empresa_id, "estado": "pendiente", "modulo": {"$in": aprobables}, "usuario_id": {"$ne": user["id"]}})
    if "contabilidad" in aprobables:
        n += await db.comprobantes_contables.count_documents({"empresa_id": empresa_id, "estado": "por_aprobar", "creado_por": {"$ne": user["id"]}})
    return {"pendientes": n}


async def _solicitud_pendiente(empresa_id: str, sid: str) -> dict:
    s = await get_db().solicitudes_aprobacion.find_one({"_id": oid(sid), "empresa_id": empresa_id})
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if s["estado"] != "pendiente":
        raise HTTPException(409, f"La solicitud ya está {s['estado']}")
    return s


@router.post("/{sid}/aprobar")
async def aprobar(sid: str, empresa_id: str = Depends(get_empresa_activa), user: dict = Depends(get_current_user)):
    """Autoriza la solicitud y la ejecuta como si la hubiera hecho su solicitante."""
    from main import app

    db = get_db()
    s = await _solicitud_pendiente(empresa_id, sid)
    if not puede_aprobar(user, s["modulo"]):
        raise HTTPException(403, "No tienes permiso para aprobar en este módulo")
    if s["usuario_id"] == user["id"]:
        raise HTTPException(403, "No puedes aprobar tu propia solicitud")
    solicitante = await db.usuarios.find_one({"_id": ObjectId(s["usuario_id"])})
    if not solicitante or solicitante.get("activo") is False:
        raise HTTPException(409, "El usuario que hizo la solicitud ya no está activo")
    token = create_access_token({"sub": s["usuario_id"], "rol": solicitante.get("rol"), "v": solicitante.get("token_version", 0)})
    marca = APROBADOR.set(user["id"])
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://interno") as c:
            resp = await c.request(
                s["metodo"], s["ruta"], content=s["cuerpo"].encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "X-Empresa-Id": empresa_id, "Content-Type": "application/json",
                         ENCABEZADO_REPLAY: SECRETO_REPLAY})
    finally:
        APROBADOR.reset(marca)
    try:
        cuerpo = resp.json()
    except ValueError:
        cuerpo = {}
    if not 200 <= resp.status_code < 300:
        detalle = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
        if not isinstance(detalle, str):
            detalle = f"error {resp.status_code}"
        await db.solicitudes_aprobacion.update_one({"_id": s["_id"]}, {"$set": {"ultimo_error": detalle}})
        raise HTTPException(409, f"No se pudo registrar el documento: {detalle}")
    resultado = {"estado_http": resp.status_code}
    if isinstance(cuerpo, dict):
        resultado.update({k: cuerpo[k] for k in ("id", "numero") if isinstance(cuerpo.get(k), str)})
    await db.solicitudes_aprobacion.update_one(
        {"_id": s["_id"]},
        {"$set": {"estado": "aprobada", "aprobado_por": user["id"], "aprobado_en": _ahora(), "resultado": resultado},
         "$unset": {"ultimo_error": ""}})
    await auditar(empresa_id, "solicitud_aprobacion", sid, resultado.get("numero"), user["id"], "aprobado", None, {"solicitud": s["descripcion"]})
    return _item(await db.solicitudes_aprobacion.find_one({"_id": s["_id"]}), user, await _nombres({s["usuario_id"], user["id"]}))


class Rechazo(BaseModel):
    motivo: str = Field(min_length=3)


@router.post("/{sid}/rechazar")
async def rechazar(sid: str, payload: Rechazo, empresa_id: str = Depends(get_empresa_activa), user: dict = Depends(get_current_user)):
    db = get_db()
    s = await _solicitud_pendiente(empresa_id, sid)
    if not puede_aprobar(user, s["modulo"]):
        raise HTTPException(403, "No tienes permiso para resolver solicitudes de este módulo")
    await db.solicitudes_aprobacion.update_one(
        {"_id": s["_id"]},
        {"$set": {"estado": "rechazada", "rechazado_por": user["id"], "rechazado_en": _ahora(), "motivo_rechazo": payload.motivo}})
    await auditar(empresa_id, "solicitud_aprobacion", sid, None, user["id"], "rechazado", None, {"solicitud": s["descripcion"], "motivo": payload.motivo})
    return _item(await db.solicitudes_aprobacion.find_one({"_id": s["_id"]}), user, await _nombres({s["usuario_id"], user["id"]}))


@router.post("/{sid}/cancelar")
async def cancelar(sid: str, empresa_id: str = Depends(get_empresa_activa), user: dict = Depends(get_current_user)):
    """El solicitante retira su propia solicitud mientras siga pendiente."""
    s = await _solicitud_pendiente(empresa_id, sid)
    if s["usuario_id"] != user["id"]:
        raise HTTPException(403, "Solo quien hizo la solicitud puede retirarla")
    await get_db().solicitudes_aprobacion.update_one({"_id": s["_id"]}, {"$set": {"estado": "cancelada", "cancelada_en": _ahora()}})
    return {"estado": "cancelada"}
