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
from core import impuestos, nit, parametros, roles, simple
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
    cache: dict[str, dict] = {}
    salida = []
    async for u in cursor:
        if u.get("rol") not in cache:
            cache[u.get("rol")] = await roles.obtener(empresa_id, u.get("rol", ""))
        salida.append(usuario_publico(u, cache[u.get("rol")]))
    return salida


async def _exigir_rol(empresa_id: str, clave: str) -> dict:
    existentes = {r["clave"]: r for r in await roles.listar(empresa_id)}
    if clave not in existentes:
        raise HTTPException(422, f"El rol «{clave}» no existe en esta empresa: créalo en Roles y permisos")
    return existentes[clave]


@usuarios_router.post("", status_code=201)
async def crear_usuario(
    payload: UsuarioCrear,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    db = get_db()
    if await db.usuarios.find_one({"email": payload.email}):
        raise HTTPException(409, "Email ya registrado")
    rol = await _exigir_rol(empresa_id, payload.rol)
    doc = payload.model_dump()
    # Solo se pueden asignar empresas a las que el administrador pertenece.
    asignadas = doc["empresa_ids"] or [empresa_id]
    ajenas = set(asignadas) - set(admin.get("empresa_ids", []))
    if ajenas:
        raise HTTPException(403, "No puedes asignar empresas a las que no perteneces")
    doc["empresa_ids"] = asignadas
    doc["password_hash"] = hash_password(doc.pop("password"))
    doc.pop("permisos", None)   # el acceso depende del rol, no del usuario
    doc["fecha_creacion"] = datetime.now(timezone.utc)
    res = await db.usuarios.insert_one(doc)
    return usuario_publico(await db.usuarios.find_one({"_id": res.inserted_id}), rol)


class UsuarioEditar(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    rol: str
    activo: bool = True
    requiere_aprobacion: bool | None = None
    empresa_ids: list[str] | None = None


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

    rol = await _exigir_rol(empresa_id, payload.rol)
    cambios: dict = {"nombre": payload.nombre, "rol": payload.rol, "activo": payload.activo,
                     "requiere_aprobacion": payload.requiere_aprobacion,
                     "fecha_actualizacion": datetime.now(timezone.utc)}
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
    if not payload.activo or payload.rol != u.get("rol"):
        cambios["token_version"] = int(u.get("token_version", 0)) + 1   # cierra sus sesiones abiertas
    await db.usuarios.update_one({"_id": u["_id"]}, {"$set": cambios}, )
    await db.usuarios.update_one({"_id": u["_id"]}, {"$unset": {"permisos": ""}})
    return usuario_publico(await db.usuarios.find_one({"_id": u["_id"]}), rol)


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


# ---------------------------------------------------------------------------
# Roles y permisos
# ---------------------------------------------------------------------------

roles_router = APIRouter(prefix="/api/configuracion/roles", tags=["configuracion:roles"])


class RolEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    permisos: dict[str, list[str]]
    requiere_aprobacion: bool = False


def _validar_permisos(permisos: dict[str, list[str]]) -> None:
    if {m for m in permisos if m not in MODULOS} or {a for acc in permisos.values() for a in acc if a not in ACCIONES}:
        raise HTTPException(422, "Permisos inválidos")


@roles_router.get("")
async def listar_roles(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    return {"roles": await roles.listar(empresa_id), "modulos": MODULOS, "acciones": ACCIONES}


@roles_router.post("", status_code=201)
async def crear_rol(
    payload: RolEntrada,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    _validar_permisos(payload.permisos)
    clave = roles.clave_de(payload.nombre)
    if not clave or clave in {r["clave"] for r in await roles.listar(empresa_id)}:
        raise HTTPException(409, "Ya existe un rol con ese nombre")
    await get_db().roles_empresa.insert_one({
        "empresa_id": empresa_id, "clave": clave, "nombre": payload.nombre.strip(), "sistema": False,
        "permisos": payload.permisos, "requiere_aprobacion": payload.requiere_aprobacion,
        "creado_por": admin["id"], "fecha_creacion": datetime.now(timezone.utc)})
    return await roles.obtener(empresa_id, clave)


@roles_router.put("/{clave}")
async def editar_rol(
    clave: str,
    payload: RolEntrada,
    empresa_id: str = Depends(get_empresa_activa),
    admin: dict = Depends(require_admin),
):
    """Cambia los permisos de un rol: aplica de inmediato a todos sus usuarios. El administrador no se puede restringir."""
    if clave == "admin":
        raise HTTPException(409, "El rol de administrador tiene siempre todos los permisos")
    if clave not in {r["clave"] for r in await roles.listar(empresa_id)}:
        raise HTTPException(404, "Rol no encontrado")
    _validar_permisos(payload.permisos)
    actual = await roles.obtener(empresa_id, clave)
    await get_db().roles_empresa.update_one(
        {"empresa_id": empresa_id, "clave": clave},
        {"$set": {"nombre": payload.nombre.strip() if not actual["sistema"] else actual["nombre"],
                  "sistema": actual["sistema"], "permisos": payload.permisos,
                  "requiere_aprobacion": payload.requiere_aprobacion,
                  "editado_por": admin["id"], "fecha_actualizacion": datetime.now(timezone.utc)}},
        upsert=True)
    return await roles.obtener(empresa_id, clave)


@roles_router.delete("/{clave}", status_code=204)
async def eliminar_rol(
    clave: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_admin),
):
    actual = await roles.obtener(empresa_id, clave)
    if actual["sistema"]:
        raise HTTPException(409, "Los roles base no se eliminan")
    if await get_db().usuarios.find_one({"empresa_ids": empresa_id, "rol": clave}):
        raise HTTPException(409, "Hay usuarios con este rol: asígnales otro antes de eliminarlo")
    await get_db().roles_empresa.delete_one({"empresa_id": empresa_id, "clave": clave})


router.include_router(roles_router)


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


@impuestos_router.post("/resoluciones-dian/sincronizar")
async def sincronizar_resoluciones(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "crear")),
):
    """Trae del portal de la DIAN (vía el proveedor tecnológico) las resoluciones habilitadas de la empresa."""
    from core.dian import resoluciones as sync
    from core.dian.cliente_pt import get_cliente_pt

    try:
        recibidas = await get_cliente_pt().listar_resoluciones(empresa_id)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    return await sync.aplicar(get_db(), empresa_id, recibidas)


@impuestos_router.get("/perfil-tributario")
async def perfil_tributario(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    """Qué impuestos y retenciones puede parametrizar la empresa activa (lo usa la interfaz)."""
    _, cap = await impuestos.empresa_y_capacidades(empresa_id)
    return cap


async def _validar_inc(payload: dict, empresa_id: str) -> None:
    """Impuesto al consumo: un solo impuesto con varias tarifas; todas se causan en la cuenta del INC."""
    payload["tipo"] = "INC"
    tarifa = float(payload.get("tarifa") or 0)
    if not 0 < tarifa <= 100:
        raise HTTPException(422, "La tarifa del impuesto debe estar entre 0 y 100")
    if not payload.get("cuenta_contable"):
        payload["cuenta_contable"] = (await parametros.obtener(empresa_id))["impuesto_consumo"]
    await parametros.validar_codigos(empresa_id, {"Cuenta contable": payload["cuenta_contable"]})


class CuentaINC(BaseModel):
    cuenta_contable: str = Field(min_length=4)


@impuestos_router.get("/impuesto-consumo/cuenta")
async def cuenta_inc(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("configuracion", "leer")),
):
    return {"cuenta_contable": (await parametros.obtener(empresa_id))["impuesto_consumo"]}


@impuestos_router.put("/impuesto-consumo/cuenta")
async def definir_cuenta_inc(
    payload: CuentaINC,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("configuracion", "editar")),
):
    """Cuenta única del impuesto al consumo: se aplica a todas sus tarifas (las ventas ya hechas conservan la suya)."""
    await parametros.validar_codigos(empresa_id, {"Cuenta del impuesto al consumo": payload.cuenta_contable})
    db = get_db()
    await db.parametros_contables.update_one(
        {"empresa_id": empresa_id},
        {"$set": {"cuentas.impuesto_consumo": payload.cuenta_contable, "actualizado_por": usuario["id"],
                  "fecha_actualizacion": datetime.now(timezone.utc)}},
        upsert=True)
    await db.impuestos_config.update_many({"empresa_id": empresa_id}, {"$set": {"cuenta_contable": payload.cuenta_contable}})
    return {"cuenta_contable": payload.cuenta_contable}


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
