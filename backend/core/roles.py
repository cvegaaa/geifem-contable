"""Roles por empresa: cada rol define los permisos por módulo y si sus documentos requieren aprobación.

Los usuarios no tienen permisos propios: su acceso es el de su rol, que se edita en Configuración › Roles y permisos.
Los cuatro roles base (administrador, contador, auxiliar y vendedor) existen siempre; la empresa puede crear otros.
"""
import re
import unicodedata

from core.auth.permissions import ACCIONES, MODULOS, PERMISOS_POR_ROL
from db import get_db

NOMBRES_BASE = {
    "admin": "Administrador",
    "contador": "Contador",
    "auxiliar": "Auxiliar contable",
    "vendedor": "Vendedor",
}
REQUIEREN_APROBACION = {"auxiliar"}


def permisos_admin() -> dict[str, list[str]]:
    return {m: ACCIONES.copy() for m in MODULOS}


def _completar(permisos: dict | None) -> dict[str, list[str]]:
    base = {m: [] for m in MODULOS}
    for m, acc in (permisos or {}).items():
        if m in base:
            base[m] = [a for a in ACCIONES if a in acc]
    return base


def por_defecto(clave: str) -> dict:
    return {
        "clave": clave, "nombre": NOMBRES_BASE.get(clave, clave), "sistema": clave in NOMBRES_BASE,
        "permisos": permisos_admin() if clave == "admin" else _completar(PERMISOS_POR_ROL.get(clave)),
        "requiere_aprobacion": clave in REQUIEREN_APROBACION,
    }


def clave_de(nombre: str) -> str:
    t = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40]


async def obtener(empresa_id: str | None, clave: str) -> dict:
    """El rol de la empresa; si aún no se personalizó, su plantilla base. Un rol desconocido no tiene permisos."""
    if empresa_id:
        doc = await get_db().roles_empresa.find_one({"empresa_id": empresa_id, "clave": clave})
        if doc and clave != "admin":
            return {"clave": clave, "nombre": doc.get("nombre", clave), "sistema": bool(doc.get("sistema")),
                    "permisos": _completar(doc.get("permisos")), "requiere_aprobacion": bool(doc.get("requiere_aprobacion"))}
    if clave in NOMBRES_BASE:
        return por_defecto(clave)
    return {"clave": clave, "nombre": clave, "sistema": False, "permisos": _completar(None), "requiere_aprobacion": False}


async def listar(empresa_id: str) -> list[dict]:
    """Roles de la empresa (los base siempre presentes), con la cantidad de usuarios de cada uno."""
    db = get_db()
    guardados = {r["clave"]: r async for r in db.roles_empresa.find({"empresa_id": empresa_id})}
    claves = list(NOMBRES_BASE) + [c for c in guardados if c not in NOMBRES_BASE]
    salida = []
    for c in claves:
        rol = await obtener(empresa_id, c)
        rol["usuarios"] = await db.usuarios.count_documents({"empresa_ids": empresa_id, "rol": c})
        salida.append(rol)
    return salida
