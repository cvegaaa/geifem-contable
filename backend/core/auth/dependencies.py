"""Dependencias FastAPI: usuario actual, empresa activa, chequeo de permisos."""
from bson import ObjectId
from fastapi import Depends, Header, HTTPException, Request, status

from config import settings
from db import get_db

from .jwt_utils import decode_token
from .permissions import permisos_efectivos


def _token_de_request(request: Request) -> str | None:
    """La sesión del navegador viaja en cookie httpOnly; integraciones pueden usar Bearer."""
    token = request.cookies.get(settings.cookie_nombre)
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def get_current_user(request: Request) -> dict:
    token = _token_de_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = decode_token(token)
        oid = ObjectId(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    user = await get_db().usuarios.find_one({"_id": oid})
    if not user or not user.get("activo", True):
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    if int(payload.get("v", 0)) != int(user.get("token_version", 0)):
        raise HTTPException(status_code=401, detail="La sesión ya no es válida: inicia sesión de nuevo")
    user["id"] = str(user.pop("_id"))
    user["permisos"] = permisos_efectivos(user.get("rol", ""), user.get("permisos"))
    return user


async def get_empresa_activa(
    x_empresa_id: str | None = Header(default=None, alias="X-Empresa-Id"),
    user: dict = Depends(get_current_user),
) -> str:
    """Toda operación de datos exige que el usuario pertenezca a la empresa, sin excepciones."""
    if not x_empresa_id:
        raise HTTPException(status_code=400, detail="Falta encabezado X-Empresa-Id")
    if x_empresa_id not in user.get("empresa_ids", []):
        raise HTTPException(status_code=403, detail="Empresa no autorizada para el usuario")
    return x_empresa_id


def require_permiso(modulo: str, accion: str):
    async def _dep(user: dict = Depends(get_current_user)):
        permisos = user.get("permisos", {})
        if accion not in permisos.get(modulo, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {modulo}:{accion}",
            )
        return user

    return _dep


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede hacer esto")
    return user
