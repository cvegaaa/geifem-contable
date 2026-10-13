"""Inventario: catálogo + bodegas + kardex por promedio ponderado por bodega."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from api._crud import crud_router
from core import impuestos, inventario, parametros
from core.auth.dependencies import get_empresa_activa, require_permiso
from core.documentos import (
    Linea,
    ahora,
    auditar,
    borrar_asientos,
    cargar_editable,
    en_transaccion,
    formatear_numero,
    marca_anulacion,
    oid,
    registrar_asientos,
    serializar,
    siguiente_consecutivo,
)
from db import get_db
from core.dinero import redondear

router = APIRouter()


async def _validar_cuentas_producto(payload: dict, empresa_id: str) -> None:
    """Cuentas contables e impuestos del producto, según el perfil tributario de la empresa."""
    # Las cuentas pertenecen al producto: si no se eligen, nace con las de respaldo de la empresa
    # (los servicios solo necesitan la de ingreso).
    respaldo = await parametros.obtener(empresa_id)
    necesarias = ["cuenta_ingreso"] + (["cuenta_inventario", "cuenta_costo"] if payload.get("inventariable", True) is not False else [])
    for campo in necesarias:
        if not payload.get(campo):
            payload[campo] = respaldo[parametros.CUENTAS_PRODUCTO[campo]]
    await parametros.validar_codigos(
        empresa_id, {c: payload.get(c) for c in parametros.CUENTAS_PRODUCTO}
    )
    _, cap = await impuestos.empresa_y_capacidades(empresa_id)

    tipo_iva = payload.get("tipo_iva") or "gravado"
    if tipo_iva not in ("gravado", "excluido", "exento"):
        raise HTTPException(422, "tipo_iva debe ser gravado, excluido o exento")
    payload["tipo_iva"] = tipo_iva
    tarifa = float(payload.get("tarifa_iva") or 0)
    if tipo_iva != "gravado":
        tarifa = 0.0
    if tarifa and not cap["cobra_iva"]:
        raise HTTPException(422, "Tu empresa no es responsable de IVA: sus productos no pueden llevar IVA")
    payload["tarifa_iva"] = tarifa

    if payload.get("concepto_retefuente_venta_id") and not cap["sufre_retefuente"]:
        raise HTTPException(
            422,
            "Tu empresa no está sujeta a retención en la fuente en sus ventas "
            "(régimen SIMPLE, art. 911 ET, o autorretenedor de renta)",
        )
    if payload.get("concepto_retefuente_compra_id") and not cap["practica_retefuente"]:
        raise HTTPException(
            422, "Tu empresa no es agente de retención en la fuente: no puede parametrizar retenciones en compras"
        )
    if payload.get("impuesto_consumo_id"):
        try:
            inc_id = oid(payload["impuesto_consumo_id"], "impuesto_consumo_id")
        except HTTPException:
            raise HTTPException(422, "Impuesto al consumo inválido")
        if not await get_db().impuestos_config.find_one(
            {"_id": inc_id, "empresa_id": empresa_id, "tipo": "INC", "activo": {"$ne": False}}
        ):
            raise HTTPException(422, "El impuesto al consumo no existe en Configuración › Impuesto al consumo")
    await impuestos.validar_concepto(
        empresa_id, payload.get("concepto_retefuente_venta_id"), "retefuente", "Retención en ventas")
    await impuestos.validar_concepto(
        empresa_id, payload.get("concepto_retefuente_compra_id"), "retefuente", "Retención en compras")


# Catálogo de productos — CRUD
router.include_router(
    crud_router(
        prefix="/api/inventario/catalogo-productos",
        coleccion="productos",
        modulo_permiso="inventario",
        tags=["inventario:catalogo"],
        # Existencias y costo los calcula el kardex, no se editan a mano.
        protegidos=("costo_promedio_ponderado",),
        validar=_validar_cuentas_producto,
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

AJUSTE = "ajuste_inventario"


class MovimientoManual(BaseModel):
    """Movimiento manual: entrada, salida o ajuste (fija la existencia de la bodega)."""
    producto_id: str
    bodega_id: str
    tipo: Literal["entrada", "salida", "ajuste"]
    cantidad: float = Field(ge=0)
    costo_unitario: float = Field(default=0, ge=0)
    fecha: str
    observaciones: str | None = None

    @model_validator(mode="after")
    def _validar(self):
        if self.tipo != "ajuste" and self.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if self.tipo == "entrada" and self.costo_unitario <= 0:
            raise ValueError("Una entrada necesita costo unitario")
        return self


class Anulacion(BaseModel):
    motivo: str | None = None


async def _valorizar_ajuste(empresa_id: str, mov: MovimientoManual, prod: dict, s) -> tuple[float, float]:
    """Diferencia en unidades (+ sobrante / - faltante) y su valor al costo."""
    costo = float(prod.get("costo_promedio_ponderado", 0))
    if mov.tipo == "entrada":
        return mov.cantidad, redondear(mov.cantidad * mov.costo_unitario, 2)
    if mov.tipo == "salida":
        return -mov.cantidad, redondear(mov.cantidad * costo, 2)
    actual = await get_db().existencias_por_bodega.find_one(
        {"empresa_id": empresa_id, "producto_id": mov.producto_id, "bodega_id": mov.bodega_id}, session=s
    )
    diferencia = mov.cantidad - float((actual or {}).get("cantidad", 0))
    costo_ajuste = mov.costo_unitario if diferencia > 0 and mov.costo_unitario else costo
    return redondear(diferencia, 6), redondear(abs(diferencia) * costo_ajuste, 2)


async def _contabilizar_ajuste(empresa_id: str, aid: str, doc: dict, prod: dict, s) -> None:
    """Sobrante: débito inventario / crédito ingreso. Faltante: débito pérdida / crédito inventario."""
    if not doc["valor"]:
        return
    p = await parametros.obtener(empresa_id, s)
    cuenta_inv = parametros.cuenta_producto(prod, "cuenta_inventario", p)
    detalle = f"Ajuste de inventario {doc['producto_nombre']}"
    if doc["diferencia"] > 0:
        lineas = [Linea(codigo=cuenta_inv, debito=doc["valor"], descripcion=detalle),
                  Linea(codigo=p["ajuste_sobrante"], credito=doc["valor"], descripcion=detalle)]
    else:
        lineas = [Linea(codigo=p["ajuste_faltante"], debito=doc["valor"], descripcion=detalle),
                  Linea(codigo=cuenta_inv, credito=doc["valor"], descripcion=detalle)]
    await registrar_asientos(empresa_id, AJUSTE, aid, doc["numero"], doc["fecha"], lineas, s)


@kardex.post("/movimientos", status_code=201)
async def registrar_movimiento(
    mov: MovimientoManual,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("inventario", "crear")),
):
    db = get_db()

    async def _tx(s):
        prod = await db.productos.find_one({"_id": oid(mov.producto_id, "producto_id"), "empresa_id": empresa_id}, session=s)
        if not prod:
            raise HTTPException(404, "Producto no encontrado")
        bodega = await db.bodegas.find_one({"_id": oid(mov.bodega_id, "bodega_id"), "empresa_id": empresa_id}, session=s)
        if not bodega:
            raise HTTPException(404, "Bodega no encontrada")
        consecutivo = await siguiente_consecutivo(empresa_id, AJUSTE, s)
        diferencia, valor = await _valorizar_ajuste(empresa_id, mov, prod, s)
        doc = {**mov.model_dump(), "empresa_id": empresa_id, "prefijo": "AI", "consecutivo": consecutivo,
               "numero": formatear_numero("AI", consecutivo), "producto_nombre": prod.get("nombre", ""),
               "bodega_nombre": bodega.get("nombre", ""), "diferencia": diferencia, "valor": valor,
               "estado": "registrado", "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.ajustes_inventario.insert_one(doc, session=s)
        aid = str(res.inserted_id)
        await _contabilizar_ajuste(empresa_id, aid, doc, prod, s)
        await inventario.registrar_movimientos(
            empresa_id, AJUSTE, aid, doc["numero"], mov.fecha,
            [{"producto_id": mov.producto_id, "bodega_id": mov.bodega_id, "tipo": mov.tipo,
              "cantidad": mov.cantidad, "costo_unitario": mov.costo_unitario}],
            s,
        )
        await auditar(empresa_id, AJUSTE, aid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.ajustes_inventario.find_one({"_id": nuevo}))


@kardex.get("/ajustes")
async def listar_ajustes(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    cursor = get_db().ajustes_inventario.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@kardex.post("/ajustes/{aid}/anular")
async def anular_ajuste(
    aid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("inventario", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("ajustes_inventario", empresa_id, aid, s)
        await borrar_asientos(empresa_id, AJUSTE, aid, s)
        await inventario.borrar_movimientos(empresa_id, AJUSTE, aid, s)
        await db.ajustes_inventario.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, AJUSTE, aid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.ajustes_inventario.find_one({"_id": oid(aid)}))


@kardex.get("/movimientos")
async def listar_movimientos(
    producto_id: str | None = Query(None),
    bodega_id: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if producto_id:
        filtro["producto_id"] = producto_id
    if bodega_id:
        filtro["bodega_id"] = bodega_id
    cursor = get_db().movimientos_inventario.find(filtro).sort([("fecha", -1), ("fecha_creacion", -1)])
    return [serializar(d) async for d in cursor]


@kardex.get("/existencias")
async def listar_existencias(
    producto_id: str | None = Query(None),
    bodega_id: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("inventario", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if producto_id:
        filtro["producto_id"] = producto_id
    if bodega_id:
        filtro["bodega_id"] = bodega_id
    return [serializar(d) async for d in get_db().existencias_por_bodega.find(filtro)]


router.include_router(kardex)
