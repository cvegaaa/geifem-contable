"""Rutas de autenticación: login, registro inicial, /me."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from db import get_db

from .dependencies import get_current_user
from .jwt_utils import create_access_token, hash_password, verify_password
from .models import LoginRequest, TokenResponse, UsuarioBase, UsuarioCrear
from .permissions import permisos_base

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioBase, status_code=201)
async def registro(payload: UsuarioCrear):
    """Crea un usuario. En Fase 1 abierto; en producción debe restringirse a admin."""
    db = get_db()
    if await db.usuarios.find_one({"email": payload.email}):
        raise HTTPException(status_code=409, detail="Email ya registrado")
    doc = payload.model_dump()
    doc["password_hash"] = hash_password(doc.pop("password"))
    if not doc.get("permisos"):
        doc["permisos"] = permisos_base(doc["rol"])
    doc["fecha_creacion"] = datetime.now(timezone.utc)
    await db.usuarios.insert_one(doc)
    return UsuarioBase(**doc)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    db = get_db()
    user = await db.usuarios.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.get("activo", True):
        raise HTTPException(status_code=403, detail="Usuario inactivo")
    token = create_access_token({"sub": str(user["_id"]), "rol": user["rol"]})
    empresa_ids = user.get("empresa_ids", [])
    return TokenResponse(
        access_token=token,
        usuario=UsuarioBase(**user),
        empresa_activa_id=empresa_ids[0] if empresa_ids else None,
    )


@router.get("/me", response_model=UsuarioBase)
async def me(user: dict = Depends(get_current_user)):
    return UsuarioBase(**user)
