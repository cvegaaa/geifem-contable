"""Alta de empresas (tenants).

Crear una empresa es atómico: documento de la empresa + PUC semilla + caja general +
bodega principal + membresía del usuario creador, todo en una transacción.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo.asynchronous.client_session import AsyncClientSession

from core.impuestos import conceptos_sugeridos
from core.puc import puc_semilla
from db import get_client, get_db


async def validar_nit_disponible(nit: str) -> None:
    if await get_db().empresas.find_one({"nit": nit}):
        raise HTTPException(409, "Ya existe una empresa con ese NIT")


async def insertar_empresa(datos: dict, usuario_id: str, s: AsyncClientSession) -> str:
    """Inserta la empresa y su configuración inicial dentro de la sesión `s`."""
    db = get_db()
    ahora = datetime.now(timezone.utc)
    res = await db.empresas.insert_one(
        {**datos, "activo": True, "creado_por": usuario_id, "fecha_creacion": ahora},
        session=s,
    )
    empresa_id = str(res.inserted_id)
    await db.plan_cuentas.insert_many(
        [
            {**c, "empresa_id": empresa_id, "activo": True, "fecha_creacion": ahora}
            for c in puc_semilla()
        ],
        session=s,
    )
    await db.bodegas.insert_one(
        {
            "empresa_id": empresa_id,
            "nombre": "Principal",
            "direccion": "",
            "es_principal": True,
            "activo": True,
            "fecha_creacion": ahora,
        },
        session=s,
    )
    await db.conceptos_retencion.insert_many(conceptos_sugeridos(empresa_id, ahora), session=s)
    await db.cajas.insert_one(
        {
            "empresa_id": empresa_id,
            "nombre": "Caja general",
            "cuenta_contable": "1105",
            "saldo_inicial": 0,
            "saldo_inicial_contabilizado": True,
            "activo": True,
            "fecha_creacion": ahora,
        },
        session=s,
    )
    await db.usuarios.update_one(
        {"_id": ObjectId(usuario_id)}, {"$addToSet": {"empresa_ids": empresa_id}}, session=s
    )
    return empresa_id


async def crear_empresa(datos: dict, usuario_id: str) -> str:
    await validar_nit_disponible(datos["nit"])

    async def _tx(s: AsyncClientSession) -> str:
        return await insertar_empresa(datos, usuario_id, s)

    async with get_client().start_session() as s:
        return await s.with_transaction(_tx)
