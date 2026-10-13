"""Routers de Configuración: catálogos CRUD, empresas y usuarios."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api._crud import crud_router
from core.auth.dependencies import (
    get_current_user,
    get_empresa_activa,
    require_admin,
    require_permiso,
)
from core.auth.jwt_utils import hash_password
from core.auth.models import EmpresaDatos, UsuarioCrear
from core.auth.permissions import ACCIONES, MODULOS, PERMISOS_POR_ROL, permisos_base
from core.auth.routes import usuario_publico
from core import impuestos, nit, parametros, simple
from core.empresas import crear_empresa
from core.documentos import oid
from db import get_db

router = APIRouter()

# Recursos CRUD estándar
RECURSOS = [
    ("/plan-cuentas", "plan_cuentas"),
    ("/terceros", "terceros"),
    ("/tipos-documento", "tipos_documento"),
    ("/resoluciones-dian", "resoluciones_dian"),
    ("/centros-costo", "centros_costo"),
    ("/unidades-medida", "unidades_medida"),
    ("/formas-pago", "formas_pago"),
]

async def _validar_tercero(payload: dict, empresa_id: str) -> None:
    """NIT: calcula el dígito de verificación y rechaza uno que no corresponda."""
    if str(payload.get("tipo_documento", "")).upper() != "NIT":
        return
    esperado = nit.digito_verificacion(payload.get("numero_documento"))
    if esperado is None:
        raise HTTPException(422, "El NIT debe ser numérico (máximo 15 dígitos)")
    dado = str(payload.get("dv") or "").strip()
    if dado and dado != esperado:
        raise HTTPException(422, f"El dígito de verificación no corresponde: para ese NIT es {esperado}")
    payload["numero_documento"] = nit.limpiar(payload["numero_documento"])
    payload["dv"] = esperado


VALIDADORES = {"terceros": _validar_tercero}

for prefix, coleccion in RECURSOS:
    router.include_router(
        crud_router(
            prefix=f"/api/configuracion{prefix}",
            coleccion=coleccion,
            modulo_permiso="configuracion",
            tags=[f"configuracion:{prefix.strip('/')}"],
            validar=VALIDADORES.get(coleccion),
        )
    )


# ---------------------------------------------------------------------------
# Empresas: el usuario solo ve y edita las empresas a las que pertenece.
# ---------------------------------------------------------------------------

empresas_router = APIRouter(
    prefix="/api/configuracion/datos-empresa", tags=["configuracion:datos-empresa"]
)


def _empresa_publica(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def _validar_pertenencia(user: dict, empresa_id: str) -> ObjectId:
    if empresa_id not in user.get("empresa_ids", []):
        raise HTTPException(404, "Empresa no encontrada")
    return ObjectId(empresa_id)


@empresas_router.get("")
async def listar_empresas(user: dict = Depends(get_current_user)):
    ids = [ObjectId(e) for e in user.get("empresa_ids", [])]
    cursor = get_db().empresas.find({"_id": {"$in": ids}}).sort("razon_social", 1)
    return [_empresa_publica(d) async for d in cursor]


@empresas_router.post("", status_code=201)
async def nueva_empresa(payload: EmpresaDatos, user: dict = Depends(require_admin)):
    empresa_id = await crear_empresa(payload.model_dump(), user["id"])
    return _empresa_publica(await get_db().empresas.find_one({"_id": ObjectId(empresa_id)}))


@empresas_router.get("/{empresa_id}")
async def obtener_empresa(empresa_id: str, user: dict = Depends(get_current_user)):
    oid = _validar_pertenencia(user, empresa_id)
    return _empresa_publica(await get_db().empresas.find_one({"_id": oid}))


@empresas_router.put("/{empresa_id}")
async def editar_empresa(
    empresa_id: str,
    payload: EmpresaDatos,
    user: dict = Depends(require_permiso("configuracion", "editar")),
):
    oid = _validar_pertenencia(user, empresa_id)
    db = get_db()
    datos = payload.model_dump()
    if await db.empresas.find_one({"nit": datos["nit"], "_id": {"$ne": oid}}):
        raise HTTPException(409, "Ya existe una empresa con ese NIT")
    datos["fecha_actualizacion"] = datetime.now(timezone.utc)
    await db.empresas.update_one({"_id": oid}, {"$set": datos})
    return _empresa_publica(await db.empresas.find_one({"_id": oid}))


router.include_router(empresas_router)


# ---------------------------------------------------------------------------
# Usuarios: acotados a la empresa activa; solo administradores los gestionan.
# ---------------------------------------------------------------------------

usuarios_router = APIRouter(
    prefix="/api/configuracion/usuarios-roles", tags=["configuracion:usuarios"]
)


@usuarios_router.get("")
async def listar_usuarios(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    cursor = get_db().usuarios.find({"empresa_ids": empresa_id}).sort("nombre", 1)
    return [usuario_publico(u) async for u in cursor]


@usuarios_router.post("", status_code=201)
async def crear_usuario(
    payload: UsuarioCrear,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    db = get_db()
    if await db.usuarios.find_one({"email": payload.email}):
        raise HTTPException(409, "Email ya registrado")
    doc = payload.model_dump()
    # Solo se pueden asignar empresas a las que el administrador pertenece.
    asignadas = doc["empresa_ids"] or [empresa_id]
    ajenas = set(asignadas) - set(admin.get("empresa_ids", []))
    if ajenas:
        raise HTTPException(403, "No puedes asignar empresas a las que no perteneces")
    doc["empresa_ids"] = asignadas
    doc["password_hash"] = hash_password(doc.pop("password"))
    if not doc.get("permisos"):
        doc["permisos"] = permisos_base(doc["rol"])
    doc["fecha_creacion"] = datetime.now(timezone.utc)
    res = await db.usuarios.insert_one(doc)
    return usuario_publico(await db.usuarios.find_one({"_id": res.inserted_id}))


class UsuarioEditar(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    rol: Literal["admin", "contador", "auxiliar", "vendedor"]
    activo: bool = True
    requiere_aprobacion: bool | None = None
    empresa_ids: list[str] | None = None
    permisos: dict[str, list[str]] | None = None


class NuevaPassword(BaseModel):
    nueva: str = Field(min_length=8)

    @field_validator("nueva")
    @classmethod
    def validar(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede superar 72 bytes")
        return v


async def _usuario_de_la_empresa(uid: str, empresa_id: str) -> dict:
    u = await get_db().usuarios.find_one({"_id": oid(uid), "empresa_ids": empresa_id})
    if not u:
        raise HTTPException(404, "Usuario no encontrado en esta empresa")
    return u


async def _quedan_admins(empresa_id: str, excluir) -> bool:
    return bool(await get_db().usuarios.find_one(
        {"_id": {"$ne": excluir}, "empresa_ids": empresa_id, "rol": "admin", "activo": {"$ne": False}}))


@usuarios_router.put("/{uid}")
async def editar_usuario(
    uid: str,
    payload: UsuarioEditar,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    """Cambia nombre, rol, permisos, empresas y estado de un usuario de la empresa activa."""
    db = get_db()
    u = await _usuario_de_la_empresa(uid, empresa_id)
    soy_yo = str(u["_id"]) == admin["id"]
    deja_de_ser_admin = u.get("rol") == "admin" and (payload.rol != "admin" or not payload.activo)
    if soy_yo and deja_de_ser_admin:
        raise HTTPException(409, "No puedes quitarte tu propio rol de administrador ni desactivarte")
    if deja_de_ser_admin and not await _quedan_admins(empresa_id, u["_id"]):
        raise HTTPException(409, "La empresa debe conservar al menos un administrador activo")

    permisos = payload.permisos
    if permisos is not None:
        desconocidos = {m for m in permisos if m not in MODULOS}
        invalidas = {a for acc in permisos.values() for a in acc if a not in ACCIONES}
        if desconocidos or invalidas:
            raise HTTPException(422, "Permisos inválidos")
    elif payload.rol != u.get("rol"):
        permisos = permisos_base(payload.rol)   # al cambiar de rol se aplica su plantilla
    cambios: dict = {"nombre": payload.nombre, "rol": payload.rol, "activo": payload.activo,
                     "requiere_aprobacion": payload.requiere_aprobacion,
                     "fecha_actualizacion": datetime.now(timezone.utc)}
    if permisos is not None:
        cambios["permisos"] = permisos
    if payload.empresa_ids is not None:
        # El administrador solo gestiona las empresas que él mismo tiene; las demás del usuario no se tocan.
        propias = set(admin.get("empresa_ids", []))
        if set(payload.empresa_ids) - propias:
            raise HTTPException(403, "No puedes asignar empresas a las que no perteneces")
        ajenas = [e for e in u.get("empresa_ids", []) if e not in propias]
        nuevas = list(dict.fromkeys([*ajenas, *payload.empresa_ids]))
        if not soy_yo and empresa_id not in nuevas and u.get("rol") == "admin" and not await _quedan_admins(empresa_id, u["_id"]):
            raise HTTPException(409, "La empresa debe conservar al menos un administrador activo")
        cambios["empresa_ids"] = nuevas
    if not payload.activo or payload.rol != u.get("rol") or permisos is not None:
        cambios["token_version"] = int(u.get("token_version", 0)) + 1   # cierra sus sesiones abiertas
    await db.usuarios.update_one({"_id": u["_id"]}, {"$set": cambios})
    return usuario_publico(await db.usuarios.find_one({"_id": u["_id"]}))


@usuarios_router.post("/{uid}/restablecer-password", status_code=204)
async def restablecer_password(
    uid: str,
    payload: NuevaPassword,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    """El administrador define una contraseña nueva; las sesiones abiertas del usuario se cierran."""
    u = await _usuario_de_la_empresa(uid, empresa_id)
    await get_db().usuarios.update_one(
        {"_id": u["_id"]},
        {"$set": {"password_hash": hash_password(payload.nueva), "token_version": int(u.get("token_version", 0)) + 1}})


@usuarios_router.get("/roles-plantilla")
async def roles_plantilla(_=Depends(require_permiso("configuracion", "leer"))):
    return PERMISOS_POR_ROL


router.include_router(usuarios_router)


# ---------------------------------------------------------------------------
# Parámetros contables: qué cuenta usa cada asiento automático.
# ---------------------------------------------------------------------------

parametros_router = APIRouter(
    prefix="/api/configuracion/parametros-contables", tags=["configuracion:parametros"]
)


class ParametrosContables(BaseModel):
    cuentas: dict[str, str]


@parametros_router.get("")
async def ver_parametros(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    vigentes = await parametros.obtener(empresa_id)
    return [
        {"clave": clave, "grupo": grupo, "descripcion": desc, "codigo": vigentes[clave], "por_defecto": defecto}
        for clave, (grupo, desc, defecto) in parametros.PARAMETROS.items()
    ]


@parametros_router.put("")
async def guardar_parametros(
    payload: ParametrosContables,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("configuracion", "editar")),
):
    desconocidas = set(payload.cuentas) - set(parametros.PARAMETROS)
    if desconocidas:
        raise HTTPException(422, f"Parámetros desconocidos: {', '.join(sorted(desconocidas))}")
    cuentas = {k: v for k, v in payload.cuentas.items() if v}
    await parametros.validar_codigos(
        empresa_id, {parametros.PARAMETROS[k][1]: v for k, v in cuentas.items()}
    )
    await get_db().parametros_contables.update_one(
        {"empresa_id": empresa_id},
        {"$set": {"cuentas": cuentas, "actualizado_por": usuario["id"],
                  "fecha_actualizacion": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return await ver_parametros(empresa_id)


router.include_router(parametros_router)


# ---------------------------------------------------------------------------
# Impuestos: perfil tributario y conceptos de retención.
# ---------------------------------------------------------------------------

impuestos_router = APIRouter(prefix="/api/configuracion", tags=["configuracion:impuestos"])


@impuestos_router.get("/perfil-tributario")
async def perfil_tributario(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    """Qué impuestos y retenciones puede parametrizar la empresa activa (lo usa la interfaz)."""
    _, cap = await impuestos.empresa_y_capacidades(empresa_id)
    return cap


async def _validar_inc(payload: dict, empresa_id: str) -> None:
    """Impuesto al consumo: cada impuesto va atado a la cuenta contable donde se causa."""
    payload["tipo"] = "INC"
    tarifa = float(payload.get("tarifa") or 0)
    if not 0 < tarifa <= 100:
        raise HTTPException(422, "La tarifa del impuesto debe estar entre 0 y 100")
    if not payload.get("cuenta_contable"):
        raise HTTPException(422, "Selecciona la cuenta contable donde se causa el impuesto")
    await parametros.validar_codigos(empresa_id, {"Cuenta contable": payload["cuenta_contable"]})


router.include_router(
    crud_router(
        prefix="/api/configuracion/impuestos",
        coleccion="impuestos_config",
        modulo_permiso="configuracion",
        tags=["configuracion:impuestos"],
        validar=_validar_inc,
    )
)


@impuestos_router.post("/plan-cuentas/cargar-sugeridas")
async def cargar_cuentas_sugeridas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "crear")),
):
    """Agrega al plan de la empresa las cuentas sugeridas que le falten (no toca las existentes)."""
    from core.puc import puc_semilla

    db = get_db()
    existentes = {c["codigo"] async for c in db.plan_cuentas.find({"empresa_id": empresa_id}, {"codigo": 1})}
    ahora = datetime.now(timezone.utc)
    nuevas = [
        {**c, "empresa_id": empresa_id, "activo": True, "fecha_creacion": ahora}
        for c in puc_semilla() if c["codigo"] not in existentes
    ]
    if nuevas:
        await db.plan_cuentas.insert_many(nuevas)
    return {"agregadas": len(nuevas), "codigos": [c["codigo"] for c in nuevas]}


async def _validar_concepto(payload: dict, empresa_id: str) -> None:
    if payload.get("tipo") not in impuestos.TIPOS_CONCEPTO:
        raise HTTPException(422, "El tipo debe ser retefuente, reteica o reteiva")
    for campo in ("tarifa", "tarifa_no_declarante", "base_uvt"):
        v = payload.get(campo)
        if v not in (None, "") and float(v) < 0:
            raise HTTPException(422, f"{campo} no puede ser negativa")
    if payload.get("tarifa") in (None, ""):
        raise HTTPException(422, "Indica la tarifa")
    await parametros.validar_codigos(empresa_id, {
        "Cuenta del pasivo (retención practicada)": payload.get("cuenta_pasivo"),
        "Cuenta a favor (retención que te practican)": payload.get("cuenta_favor"),
    })
    payload.pop("sugerido", None)


router.include_router(
    crud_router(
        prefix="/api/configuracion/conceptos-retencion",
        coleccion="conceptos_retencion",
        modulo_permiso="configuracion",
        tags=["configuracion:conceptos-retencion"],
        validar=_validar_concepto,
    )
)


@impuestos_router.post("/conceptos-retencion/cargar-sugeridos")
async def cargar_conceptos_sugeridos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "crear")),
):
    """Agrega los conceptos sugeridos que la empresa aún no tiene (no toca los existentes)."""
    db = get_db()
    existentes = {(c["tipo"], c["nombre"]) async for c in db.conceptos_retencion.find({"empresa_id": empresa_id})}
    nuevos = [c for c in impuestos.conceptos_sugeridos(empresa_id, datetime.now(timezone.utc))
              if (c["tipo"], c["nombre"]) not in existentes]
    if nuevos:
        await db.conceptos_retencion.insert_many(nuevos)
    return {"agregados": len(nuevos)}


router.include_router(impuestos_router)


# ---------------------------------------------------------------------------
# Tarifas del régimen SIMPLE
# ---------------------------------------------------------------------------

tarifas_simple_router = APIRouter(prefix="/api/configuracion/tarifas-simple", tags=["configuracion:tarifas-simple"])


class TarifasSimple(BaseModel):
    verificado: bool = False
    grupos: dict[str, dict]


@tarifas_simple_router.get("")
async def obtener_tarifas_simple(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    return await simple.obtener(empresa_id)


@tarifas_simple_router.put("")
async def guardar_tarifas_simple(
    payload: TarifasSimple,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "editar")),
):
    simple.validar(payload.grupos)
    await get_db().tarifas_simple.update_one(
        {"empresa_id": empresa_id},
        {"$set": {"verificado": payload.verificado, "grupos": payload.grupos}},
        upsert=True,
    )
    return await simple.obtener(empresa_id)


router.include_router(tarifas_simple_router)
