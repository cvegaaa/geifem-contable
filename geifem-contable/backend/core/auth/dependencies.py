"""Dependencias FastAPI: usuario actual, empresa activa, chequeo de permisos."""
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from db import get_db

from .jwt_utils import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sin sujeto")
    db = get_db()
    from bson import ObjectId

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Sujeto inválido")
    user = await db.usuarios.find_one({"_id": oid})
    if not user or not user.get("activo", True):
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    user["id"] = str(user.pop("_id"))
    return user


async def get_empresa_activa(
    x_empresa_id: str | None = Header(default=None, alias="X-Empresa-Id"),
    user: dict = Depends(get_current_user),
) -> str:
    if not x_empresa_id:
        raise HTTPException(status_code=400, detail="Falta encabezado X-Empresa-Id")
    if user["rol"] != "admin" and x_empresa_id not in user.get("empresa_ids", []):
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
