"""Inventario FASE 1: catálogo de productos + kardex PP (base) + sync stub."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api._crud import crud_router
from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter()

# Catálogo — CRUD completo
router.include_router(
    crud_router(
        prefix="/api/inventario/catalogo-productos",
        coleccion="productos",
        modulo_permiso="inventario",
        tags=["inventario:catalogo"],
    )
)


kardex = APIRouter(prefix="/api/inventario/kardex", tags=["inventario:kardex"])


class MovimientoInventario(BaseModel):
    producto_id: str
    tipo: str  # entrada | salida | ajuste
    cantidad: float
    costo_unitario: float
    fecha: str
    referencia_documento: str | None = None


@kardex.post("/movimientos", status_code=201)
async def registrar_movimiento(
    mov: MovimientoInventario,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "crear")),
):
    """Registra un movimiento y recalcula costo promedio ponderado."""
    if mov.tipo not in {"entrada", "salida", "ajuste"}:
        raise HTTPException(422, "Tipo inválido")

    db = get_db()
    prod = await db.productos.find_one({"_id": ObjectId(mov.producto_id), "empresa_id": empresa_id})
    if not prod:
        raise HTTPException(404, "Producto no encontrado")

    existencia_actual = float(prod.get("existencia", 0))
    costo_actual = float(prod.get("costo_promedio_ponderado", 0))

    if mov.tipo == "entrada":
        nueva_existencia = existencia_actual + mov.cantidad
        if nueva_existencia > 0:
            nuevo_costo = (
                (existencia_actual * costo_actual) + (mov.cantidad * mov.costo_unitario)
            ) / nueva_existencia
        else:
            nuevo_costo = mov.costo_unitario
    elif mov.tipo == "salida":
        if mov.cantidad > existencia_actual:
            raise HTTPException(409, "Existencia insuficiente")
        nueva_existencia = existencia_actual - mov.cantidad
        nuevo_costo = costo_actual  # PP no cambia en salidas
    else:  # ajuste: reemplaza existencia y costo
        nueva_existencia = mov.cantidad
        nuevo_costo = mov.costo_unitario

    await db.productos.update_one(
        {"_id": prod["_id"]},
        {"$set": {"existencia": nueva_existencia, "costo_promedio_ponderado": round(nuevo_costo, 6)}},
    )
    doc = mov.model_dump()
    doc.update({"empresa_id": empresa_id, "fecha_creacion": datetime.now(timezone.utc)})
    await db.movimientos_inventario.insert_one(doc)
    return {"ok": True, "existencia": nueva_existencia, "costo_promedio_ponderado": nuevo_costo}


@kardex.get("/movimientos")
async def listar_movimientos(
    producto_id: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    db = get_db()
    filtro = {"empresa_id": empresa_id}
    if producto_id:
        filtro["producto_id"] = producto_id
    return [
        {**d, "id": str(d.pop("_id"))}
        async for d in db.movimientos_inventario.find(filtro).sort("fecha", -1)
    ]


router.include_router(kardex)


# Sync POS/Online: stub Fase 1 (contrato listo)
sync = APIRouter(prefix="/api/inventario/sync", tags=["inventario:sync"])


@sync.post("/pos-online")
async def sync_pos_online(_=Depends(require_permiso("inventario", "editar"))):
    return {"ok": True, "detail": "Sincronización POS/Online — pendiente configuración de canal"}


router.include_router(sync)
