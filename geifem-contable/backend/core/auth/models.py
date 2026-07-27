"""Modelos Pydantic para autenticación y usuarios."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "contador", "vendedor"]


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: str
    rol: Role
    empresa_ids: list[str] = Field(default_factory=list)
    permisos: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapa modulo -> [acciones]. Ej: {'facturacion': ['leer','crear']}",
    )
    activo: bool = True


class UsuarioCrear(UsuarioBase):
    password: str


class UsuarioEnDB(UsuarioBase):
    id: str
    password_hash: str
    fecha_creacion: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioBase
    empresa_activa_id: str | None = None
