"""Kardex por promedio ponderado.

Los movimientos (`movimientos_inventario`) son la fuente de verdad. Las
existencias por bodega y el costo promedio del producto se recalculan
reproduciendo los movimientos en orden cronológico, de modo que editar o
anular un documento antiguo deja el kardex coherente.
"""
from collections import defaultdict

from fastapi import HTTPException
from pymongo.asynchronous.client_session import AsyncClientSession

from core import parametros
from core.documentos import Linea, ahora, borrar_asientos, oid, registrar_asientos
from db import get_db
from core.dinero import redondear

TIPOS = ("entrada", "salida", "ajuste")

# Asiento que corrige el costo de venta cuando el kardex se recalcula (compra con fecha anterior, edición de costos).
AJUSTE_COSTO = "ajuste_costo"


async def registrar_movimientos(
    empresa_id: str, documento_tipo: str, documento_id: str, numero: str, fecha: str,
    movimientos: list[dict], s: AsyncClientSession,
) -> set[str]:
    """Inserta movimientos [{producto_id, bodega_id, tipo, cantidad, costo_unitario}] y recalcula."""
    if not movimientos:
        return set()
    momento = ahora()
    docs = [
        {
            "empresa_id": empresa_id,
            "producto_id": m["producto_id"],
            "bodega_id": m["bodega_id"],
            "tipo": m["tipo"],
            "cantidad": float(m["cantidad"]),
            "costo_unitario": float(m.get("costo_unitario") or 0),
            "fecha": fecha,
            "referencia_documento": numero,
            "documento_tipo": documento_tipo,
            "documento_id": documento_id,
            "fecha_creacion": momento,
        }
        for m in movimientos
    ]
    await get_db().movimientos_inventario.insert_many(docs, session=s)
    productos = {m["producto_id"] for m in movimientos}
    await recalcular(empresa_id, productos, s)
    return productos


async def borrar_movimientos(
    empresa_id: str, documento_tipo: str, documento_id: str, s: AsyncClientSession,
    recalcular_despues: bool = True,
) -> set[str]:
    db = get_db()
    filtro = {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id}
    productos = set()
    async for m in db.movimientos_inventario.find(filtro, session=s):
        productos.add(m["producto_id"])
        if m.get("valor_contabilizado") is not None:
            await borrar_asientos(empresa_id, AJUSTE_COSTO, str(m["_id"]), s)
    await db.movimientos_inventario.delete_many(filtro, session=s)
    if recalcular_despues:
        await recalcular(empresa_id, productos, s)
    return productos


async def recalcular(empresa_id: str, producto_ids: set[str], s: AsyncClientSession) -> None:
    db = get_db()
    for producto_id in producto_ids:
        producto = await db.productos.find_one(
            {"_id": oid(producto_id, "producto_id"), "empresa_id": empresa_id}, session=s
        )
        nombre = producto.get("nombre", producto_id) if producto else producto_id
        por_bodega: dict[str, float] = defaultdict(float)
        total = 0.0
        costo = 0.0
        cursor = db.movimientos_inventario.find(
            {"empresa_id": empresa_id, "producto_id": producto_id}, session=s
        ).sort([("fecha", 1), ("fecha_creacion", 1), ("_id", 1)])
        async for m in cursor:
            cant = float(m["cantidad"])
            bodega = m["bodega_id"]
            if m["tipo"] == "entrada":
                nuevo_total = total + cant
                if nuevo_total > 0:
                    costo = (total * costo + cant * float(m["costo_unitario"])) / nuevo_total
                total = nuevo_total
                por_bodega[bodega] += cant
            elif m["tipo"] == "salida":
                if cant > por_bodega[bodega] + 1e-9:
                    raise HTTPException(
                        409,
                        f"Existencia insuficiente de «{nombre}» al {m['fecha']}: "
                        f"hay {redondear(por_bodega[bodega], 4)} y se requieren {cant}",
                    )
                por_bodega[bodega] -= cant
                total -= cant
                # La salida se valora al costo promedio vigente en su fecha.
                if abs(float(m.get("costo_unitario") or 0) - costo) > 1e-6:
                    await db.movimientos_inventario.update_one(
                        {"_id": m["_id"]}, {"$set": {"costo_unitario": redondear(costo, 6)}}, session=s
                    )
            else:  # ajuste: fija la existencia de la bodega y, si se indica, el costo
                total += cant - por_bodega[bodega]
                por_bodega[bodega] = cant
                if float(m.get("costo_unitario") or 0) > 0:
                    costo = float(m["costo_unitario"])

        momento = ahora()
        bodegas_previas = {
            e["bodega_id"]
            async for e in db.existencias_por_bodega.find(
                {"empresa_id": empresa_id, "producto_id": producto_id}, session=s
            )
        }
        for bodega in bodegas_previas | set(por_bodega):
            await db.existencias_por_bodega.update_one(
                {"empresa_id": empresa_id, "producto_id": producto_id, "bodega_id": bodega},
                {"$set": {"cantidad": redondear(por_bodega.get(bodega, 0.0), 6), "fecha_actualizacion": momento}},
                upsert=True,
                session=s,
            )
        if producto:
            await db.productos.update_one(
                {"_id": producto["_id"]},
                {"$set": {"costo_promedio_ponderado": redondear(costo, 6)}},
                session=s,
            )
    await reajustar_costos(empresa_id, producto_ids, s)


async def marcar_contabilizado(empresa_id: str, documento_tipo: str, documento_id: str, s: AsyncClientSession) -> dict[str, float]:
    """Fija el valor de costo que el documento llevó a su asiento (base del ajuste posterior).

    Devuelve el costo unitario vigente de cada producto del documento (ya valorado por el kardex).
    """
    db = get_db()
    costos: dict[str, float] = {}
    filtro = {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id, "tipo": "salida"}
    async for m in db.movimientos_inventario.find(filtro, session=s):
        costo = float(m.get("costo_unitario") or 0)
        costos[m["producto_id"]] = costo
        await db.movimientos_inventario.update_one(
            {"_id": m["_id"]}, {"$set": {"valor_contabilizado": redondear(float(m["cantidad"]) * costo, 2)}}, session=s)
    return costos


async def reajustar_costos(empresa_id: str, producto_ids: set[str], s: AsyncClientSession) -> None:
    """Si el costo de una salida ya contabilizada cambió, deja un asiento de ajuste por la diferencia."""
    if not producto_ids:
        return
    db = get_db()
    params = None
    async for m in db.movimientos_inventario.find(
        {"empresa_id": empresa_id, "producto_id": {"$in": list(producto_ids)}, "tipo": "salida",
         "valor_contabilizado": {"$ne": None}}, session=s):
        nuevo = redondear(float(m["cantidad"]) * float(m.get("costo_unitario") or 0), 2)
        delta = redondear(nuevo - float(m["valor_contabilizado"]), 2)
        mid = str(m["_id"])
        previo = await db.asientos_contables.find_one(
            {"empresa_id": empresa_id, "documento_tipo": AJUSTE_COSTO, "documento_id": mid}, session=s)
        if abs(delta) < 0.005 and not previo:
            continue
        await borrar_asientos(empresa_id, AJUSTE_COSTO, mid, s)
        if abs(delta) < 0.005:
            continue
        if params is None:
            params = await parametros.obtener(empresa_id, s)
        prod = await db.productos.find_one({"_id": oid(m["producto_id"]), "empresa_id": empresa_id}, session=s)
        costo = parametros.cuenta_producto(prod, "cuenta_costo", params)
        inv = parametros.cuenta_producto(prod, "cuenta_inventario", params)
        detalle = f"Ajuste de costo de venta {m.get('referencia_documento', '')}"
        mas = delta > 0
        lineas = [Linea(codigo=costo if mas else inv, debito=abs(delta), descripcion=detalle),
                  Linea(codigo=inv if mas else costo, credito=abs(delta), descripcion=detalle)]
        await registrar_asientos(empresa_id, AJUSTE_COSTO, mid, f"AC {m.get('referencia_documento', '')}", m["fecha"], lineas, s)


async def costo_promedio(empresa_id: str, producto_id: str, s: AsyncClientSession) -> float:
    p = await get_db().productos.find_one(
        {"_id": oid(producto_id, "producto_id"), "empresa_id": empresa_id}, session=s
    )
    return float(p.get("costo_promedio_ponderado", 0)) if p else 0.0


async def bodega_principal(empresa_id: str, s: AsyncClientSession | None = None) -> str:
    db = get_db()
    b = await db.bodegas.find_one(
        {"empresa_id": empresa_id, "es_principal": True, "activo": {"$ne": False}}, session=s
    ) or await db.bodegas.find_one({"empresa_id": empresa_id, "activo": {"$ne": False}}, session=s)
    if not b:
        raise HTTPException(409, "La empresa no tiene bodegas activas")
    return str(b["_id"])
