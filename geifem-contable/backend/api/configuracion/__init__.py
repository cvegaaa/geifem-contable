"""Routers CRUD para todos los sub-módulos de Configuración (FASE 1)."""
from fastapi import APIRouter

from api._crud import crud_router

router = APIRouter()

RECURSOS = [
    ("/plan-cuentas", "plan_cuentas"),
    ("/terceros", "terceros"),
    ("/tipos-documento", "tipos_documento"),
    ("/resoluciones-dian", "resoluciones_dian"),
    ("/centros-costo", "centros_costo"),
    ("/impuestos", "impuestos_config"),
    ("/unidades-medida", "unidades_medida"),
    ("/formas-pago", "formas_pago"),
    ("/datos-empresa", "empresas"),
]

for prefix, coleccion in RECURSOS:
    router.include_router(
        crud_router(
            prefix=f"/api/configuracion{prefix}",
            coleccion=coleccion,
            modulo_permiso="configuracion",
            tags=[f"configuracion:{prefix.strip('/')}"],
        )
    )


# usuarios-roles: CRUD limitado (crear/editar/inactivar) sobre colección usuarios
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from core.auth.dependencies import require_permiso
from core.auth.jwt_utils import hash_password
from core.auth.models import UsuarioBase, UsuarioCrear
from core.auth.permissions import PERMISOS_POR_ROL, permisos_base
from db import get_db

usuarios_router = APIRouter(prefix="/api/configuracion/usuarios-roles", tags=["configuracion:usuarios"])


@usuarios_router.get("")
async def listar_usuarios(_=Depends(require_permiso("configuracion", "leer"))):
    db = get_db()
    return [
        {**u, "id": str(u.pop("_id")), "password_hash": None}
        async for u in db.usuarios.find({})
    ]


@usuarios_router.post("", status_code=201)
async def crear_usuario(
    payload: UsuarioCrear, _=Depends(require_permiso("configuracion", "crear"))
):
    db = get_db()
    if await db.usuarios.find_one({"email": payload.email}):
        raise HTTPException(409, "Email ya registrado")
    doc = payload.model_dump()
    doc["password_hash"] = hash_password(doc.pop("password"))
    if not doc.get("permisos"):
        doc["permisos"] = permisos_base(doc["rol"])
    doc["fecha_creacion"] = datetime.now(timezone.utc)
    await db.usuarios.insert_one(doc)
    return UsuarioBase(**doc)


@usuarios_router.get("/roles-plantilla")
async def roles_plantilla(_=Depends(require_permiso("configuracion", "leer"))):
    return PERMISOS_POR_ROL


router.include_router(usuarios_router)
