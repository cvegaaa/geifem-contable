"""Rutas de autenticación: registro (usuario + empresa), login, logout, /me."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.asynchronous.client_session import AsyncClientSession

from config import settings
from core.empresas import insertar_empresa, validar_nit_disponible
from db import get_client, get_db

from .dependencies import get_current_user
from .jwt_utils import create_access_token, hash_password, verify_password
from .limites import (
    exigir_cupo_login, exigir_cupo_registro, ip_cliente, limpiar, registrar_fallo_login,
)
from .models import CambioPassword, LoginRequest, RegistroRequest, SesionResponse, UsuarioPublico
from core import roles
from .permissions import permisos_base

router = APIRouter(prefix="/api/auth", tags=["auth"])


def usuario_publico(user: dict, rol: dict | None = None) -> UsuarioPublico:
    """`rol`: el rol del usuario en la empresa (de ahí salen sus permisos); sin él se usa la plantilla base."""
    datos = {k: v for k, v in user.items() if k not in ("_id", "password_hash")}
    datos["id"] = str(user.get("_id", user.get("id")))
    rol = rol or roles.por_defecto(datos.get("rol", ""))
    datos["permisos"] = rol["permisos"]
    datos["rol_nombre"] = rol["nombre"]
    marca = datos.get("requiere_aprobacion")
    datos["aprobacion_requerida"] = bool(marca) if marca is not None else bool(rol["requiere_aprobacion"])
    return UsuarioPublico(**datos)


def _abrir_sesion(response: Response, usuario_id: str, rol: str, version: int = 0) -> None:
    # `v` es la versión de credenciales: cambiar la contraseña invalida las sesiones anteriores.
    token = create_access_token({"sub": usuario_id, "rol": rol, "v": version})
    response.set_cookie(
        settings.cookie_nombre,
        token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/registro", response_model=SesionResponse, status_code=201)
async def registro(payload: RegistroRequest, request: Request, response: Response):
    """Crea la cuenta del dueño junto con su primera empresa (queda como admin de ella)."""
    if not settings.registro_abierto:
        raise HTTPException(403, "El registro público está deshabilitado")
    await exigir_cupo_registro(ip_cliente(request))
    db = get_db()
    if await db.usuarios.find_one({"email": payload.email}):
        raise HTTPException(409, "Email ya registrado")
    await validar_nit_disponible(payload.empresa.nit)

    usuario_doc = {
        "email": payload.email,
        "nombre": payload.nombre,
        "rol": "admin",
        "empresa_ids": [],
        "permisos": permisos_base("admin"),
        "activo": True,
        "password_hash": hash_password(payload.password),
        "fecha_creacion": datetime.now(timezone.utc),
    }

    async def _tx(s: AsyncClientSession) -> str:
        res = await db.usuarios.insert_one(dict(usuario_doc), session=s)
        usuario_id = str(res.inserted_id)
        await insertar_empresa(payload.empresa.model_dump(), usuario_id, s)
        return usuario_id

    async with get_client().start_session() as s:
        usuario_id = await s.with_transaction(_tx)

    user = await db.usuarios.find_one({"_id": ObjectId(usuario_id)})
    _abrir_sesion(response, usuario_id, "admin")
    rol = await roles.obtener(user["empresa_ids"][0], "admin")
    return SesionResponse(usuario=usuario_publico(user, rol), empresa_activa_id=user["empresa_ids"][0])


@router.post("/login", response_model=SesionResponse)
async def login(payload: LoginRequest, request: Request, response: Response):
    ip = ip_cliente(request)
    await exigir_cupo_login(payload.email, ip)
    user = await get_db().usuarios.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await registrar_fallo_login(payload.email, ip)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.get("activo", True):
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    await limpiar(f"login:{payload.email.lower()}")
    _abrir_sesion(response, str(user["_id"]), user["rol"], user.get("token_version", 0))
    empresa_ids = user.get("empresa_ids", [])
    rol = await roles.obtener(empresa_ids[0] if empresa_ids else None, user["rol"])
    return SesionResponse(
        usuario=usuario_publico(user, rol),
        empresa_activa_id=empresa_ids[0] if empresa_ids else None,
    )


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(settings.cookie_nombre, path="/")


@router.post("/cambiar-password", status_code=204)
async def cambiar_password(payload: CambioPassword, response: Response, user: dict = Depends(get_current_user)):
    """Cambia la contraseña propia y cierra las demás sesiones abiertas."""
    db = get_db()
    doc = await db.usuarios.find_one({"_id": ObjectId(user["id"])})
    if not verify_password(payload.actual, doc.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    version = int(doc.get("token_version", 0)) + 1
    await db.usuarios.update_one(
        {"_id": doc["_id"]}, {"$set": {"password_hash": hash_password(payload.nueva), "token_version": version}})
    _abrir_sesion(response, user["id"], user["rol"], version)


@router.get("/me", response_model=UsuarioPublico)
async def me(user: dict = Depends(get_current_user)):
    return usuario_publico(user, {"permisos": user["permisos"], "nombre": user["rol_nombre"],
                                  "requiere_aprobacion": user["rol_requiere_aprobacion"]})
