"""Inventario FASE 1: catálogo + bodegas + kardex PP por bodega + sync stub."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api._crud import crud_router
from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter()


async def crear_bodega_principal(_empresa_doc: dict, empresa_id: str) -> None:
    """Hook: al crear una empresa nueva, generar bodega 'Principal' por defecto."""
    db = get_db()
    ya_existe = await db.bodegas.find_one({"empresa_id": empresa_id})
    if ya_existe:
        return
    await db.bodegas.insert_one(
        {
            "empresa_id": empresa_id,
            "nombre": "Principal",
            "direccion": "",
            "activo": True,
            "es_principal": True,
            "fecha_creacion": datetime.now(timezone.utc),
        }
    )


# Catálogo de productos — CRUD
router.include_router(
    crud_router(
        prefix="/api/inventario/catalogo-productos",
        coleccion="productos",
        modulo_permiso="inventario",
        tags=["inventario:catalogo"],
    )
)

# Bodegas — CRUD
router.include_router(
    crud_router(
        prefix="/api/inventario/bodegas",
        coleccion="bodegas",
        modulo_permiso="inventario",
        tags=["inventario:bodegas"],
    )
)


kardex = APIRouter(prefix="/api/inventario/kardex", tags=["inventario:kardex"])


class MovimientoInventario(BaseModel):
    producto_id: str
    bodega_id: str
    tipo: str  # entrada | salida | ajuste | traslado (traslado: F2, aún no implementado)
    cantidad: float
    costo_unitario: float
    fecha: str
    referencia_documento: str | None = None
    # Solo para traslado (F2)
    bodega_destino_id: str | None = None


async def _existencia_por_bodega(db, empresa_id: str, producto_id: str, bodega_id: str) -> float:
    doc = await db.existencias_por_bodega.find_one(
        {"empresa_id": empresa_id, "producto_id": producto_id, "bodega_id": bodega_id}
    )
    return float(doc["cantidad"]) if doc else 0.0


async def _set_existencia_por_bodega(
    db, empresa_id: str, producto_id: str, bodega_id: str, cantidad: float
) -> None:
    await db.existencias_por_bodega.update_one(
        {"empresa_id": empresa_id, "producto_id": producto_id, "bodega_id": bodega_id},
        {"$set": {"cantidad": cantidad, "fecha_actualizacion": datetime.now(timezone.utc)}},
        upsert=True,
    )


@kardex.post("/movimientos", status_code=201)
async def registrar_movimiento(
    mov: MovimientoInventario,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "crear")),
):
    """Registra un movimiento por bodega y recalcula el costo PP global del producto."""
    if mov.tipo not in {"entrada", "salida", "ajuste", "traslado"}:
        raise HTTPException(422, "Tipo inválido")
    if mov.tipo == "traslado":
        # Reservado para Fase 2 (movimiento entre bodegas de la misma empresa).
        raise HTTPException(
            status_code=501,
            detail="Traslado entre bodegas — pendiente (Fase 2).",
        )

    db = get_db()
    prod = await db.productos.find_one(
        {"_id": ObjectId(mov.producto_id), "empresa_id": empresa_id}
    )
    if not prod:
        raise HTTPException(404, "Producto no encontrado")

    bodega = await db.bodegas.find_one(
        {"_id": ObjectId(mov.bodega_id), "empresa_id": empresa_id}
    )
    if not bodega:
        raise HTTPException(404, "Bodega no encontrada")

    existencia_bodega = await _existencia_por_bodega(
        db, empresa_id, mov.producto_id, mov.bodega_id
    )
    # Existencia total del producto para el cálculo del PP global
    total_prev = 0.0
    async for d in db.existencias_por_bodega.find(
        {"empresa_id": empresa_id, "producto_id": mov.producto_id}
    ):
        total_prev += float(d.get("cantidad", 0))
    costo_actual = float(prod.get("costo_promedio_ponderado", 0))

    if mov.tipo == "entrada":
        nueva_bodega = existencia_bodega + mov.cantidad
        nueva_total = total_prev + mov.cantidad
        if nueva_total > 0:
            nuevo_costo = (
                (total_prev * costo_actual) + (mov.cantidad * mov.costo_unitario)
            ) / nueva_total
        else:
            nuevo_costo = mov.costo_unitario
    elif mov.tipo == "salida":
        if mov.cantidad > existencia_bodega:
            raise HTTPException(409, "Existencia insuficiente en la bodega")
        nueva_bodega = existencia_bodega - mov.cantidad
        nuevo_costo = costo_actual  # PP no cambia en salidas
    else:  # ajuste: reemplaza la existencia de la bodega y refresca costo
        nueva_bodega = mov.cantidad
        nuevo_costo = mov.costo_unitario

    await _set_existencia_por_bodega(
        db, empresa_id, mov.producto_id, mov.bodega_id, nueva_bodega
    )
    await db.productos.update_one(
        {"_id": prod["_id"]},
        {"$set": {"costo_promedio_ponderado": round(nuevo_costo, 6)}},
    )
    doc = mov.model_dump()
    doc.update({"empresa_id": empresa_id, "fecha_creacion": datetime.now(timezone.utc)})
    await db.movimientos_inventario.insert_one(doc)
    return {
        "ok": True,
        "existencia_bodega": nueva_bodega,
        "costo_promedio_ponderado": nuevo_costo,
    }


@kardex.get("/movimientos")
async def listar_movimientos(
    producto_id: str | None = Query(None),
    bodega_id: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    db = get_db()
    filtro: dict = {"empresa_id": empresa_id}
    if producto_id:
        filtro["producto_id"] = producto_id
    if bodega_id:
        filtro["bodega_id"] = bodega_id
    return [
        {**d, "id": str(d.pop("_id"))}
        async for d in db.movimientos_inventario.find(filtro).sort("fecha", -1)
    ]


@kardex.get("/existencias")
async def listar_existencias(
    producto_id: str | None = Query(None),
    bodega_id: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    db = get_db()
    filtro: dict = {"empresa_id": empresa_id}
    if producto_id:
        filtro["producto_id"] = producto_id
    if bodega_id:
        filtro["bodega_id"] = bodega_id
    return [
        {**d, "id": str(d.pop("_id"))}
        async for d in db.existencias_por_bodega.find(filtro)
    ]


router.include_router(kardex)


# Sync POS/Online: stub Fase 1 (contrato listo)
sync = APIRouter(prefix="/api/inventario/sync", tags=["inventario:sync"])


@sync.post("/pos-online")
async def sync_pos_online(_=Depends(require_permiso("inventario", "editar"))):
    return {"ok": True, "detail": "Sincronización POS/Online — pendiente configuración de canal"}


router.include_router(sync)
