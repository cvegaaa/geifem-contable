"""Compras — FASE 2.

Ciclo implementado:
  Orden de compra -> Recepción de mercancía (entrada a bodega) ->
  Factura de proveedor (con retenciones) -> asiento contable espejo.

Conceptos de retención se administran como catálogo CRUD.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api._crud import crud_router
from api.inventario import _existencia_por_bodega, _set_existencia_por_bodega
from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter()

compras = APIRouter(prefix="/api/compras", tags=["compras"])


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def _oid(valor: str, campo: str) -> ObjectId:
    try:
        return ObjectId(valor)
    except Exception:
        raise HTTPException(400, f"{campo} inválido")


async def _cuenta_puc(db, empresa_id: str, codigo: str) -> str | None:
    doc = await db.plan_cuentas.find_one({"empresa_id": empresa_id, "codigo": codigo})
    return str(doc["_id"]) if doc else None


@compras.get("/health")
async def health():
    return {"ok": True, "modulo": "compras", "fase": 2}


# ---------------------------------------------------------------------------
# Órdenes de compra
# ---------------------------------------------------------------------------

class ItemCompra(BaseModel):
    producto_id: str | None = None
    descripcion: str
    cantidad: float
    costo_unitario: float
    tarifa_iva: float = 0


class OrdenCompraCrear(BaseModel):
    proveedor_id: str
    fecha: str
    bodega_id: str | None = None
    observaciones: str | None = None
    items: list[ItemCompra] = Field(min_length=1)


def _totalizar(items: list[ItemCompra]) -> tuple[list[dict], float, float, float]:
    calc, subtotal, iva_total = [], 0.0, 0.0
    for it in items:
        if it.cantidad <= 0 or it.costo_unitario < 0:
            raise HTTPException(422, "Cantidad o costo inválido")
        ls = it.cantidad * it.costo_unitario
        li = ls * (it.tarifa_iva / 100)
        calc.append({**it.model_dump(), "subtotal": round(ls, 2),
                     "iva": round(li, 2), "total": round(ls + li, 2)})
        subtotal += ls
        iva_total += li
    return calc, round(subtotal, 2), round(iva_total, 2), round(subtotal + iva_total, 2)


async def _proveedor(db, empresa_id: str, proveedor_id: str) -> dict:
    doc = await db.terceros.find_one(
        {"_id": _oid(proveedor_id, "proveedor_id"), "empresa_id": empresa_id}
    )
    if not doc:
        raise HTTPException(404, "Proveedor no encontrado")
    return doc


@compras.get("/ordenes-compra")
async def listar_ordenes(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.ordenes_compra.find({"empresa_id": empresa_id}).sort("fecha", -1)]


@compras.post("/ordenes-compra", status_code=201)
async def crear_orden(
    payload: OrdenCompraCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()
    proveedor = await _proveedor(db, empresa_id, payload.proveedor_id)
    items, subtotal, iva_total, total = _totalizar(payload.items)
    consecutivo = await db.ordenes_compra.count_documents({"empresa_id": empresa_id}) + 1
    doc = {
        "empresa_id": empresa_id,
        "consecutivo": consecutivo,
        "proveedor_id": payload.proveedor_id,
        "proveedor_nombre": proveedor.get("nombre", ""),
        "fecha": payload.fecha,
        "bodega_id": payload.bodega_id,
        "items": items,
        "subtotal": subtotal,
        "iva_total": iva_total,
        "total": total,
        "estado": "abierta",
        "observaciones": payload.observaciones,
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.ordenes_compra.insert_one(doc)
    return _serialize(await db.ordenes_compra.find_one({"_id": res.inserted_id}))


@compras.get("/ordenes-compra/{oc_id}")
async def obtener_orden(
    oc_id: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    db = get_db()
    doc = await db.ordenes_compra.find_one({"_id": _oid(oc_id, "id"), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Orden no encontrada")
    return _serialize(doc)


@compras.post("/ordenes-compra/{oc_id}/anular")
async def anular_orden(
    oc_id: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "editar")),
):
    db = get_db()
    r = await db.ordenes_compra.update_one(
        {"_id": _oid(oc_id, "id"), "empresa_id": empresa_id, "estado": "abierta"},
        {"$set": {"estado": "anulada"}},
    )
    if not r.matched_count:
        raise HTTPException(409, "Solo se pueden anular órdenes abiertas")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Recepción de mercancía (entrada a bodega)
# ---------------------------------------------------------------------------

class ItemRecepcion(BaseModel):
    producto_id: str
    cantidad: float
    costo_unitario: float


class RecepcionCrear(BaseModel):
    orden_compra_id: str | None = None
    bodega_id: str
    fecha: str
    observaciones: str | None = None
    items: list[ItemRecepcion] = Field(min_length=1)


@compras.get("/recepcion-mercancia")
async def listar_recepciones(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.recepciones_mercancia.find({"empresa_id": empresa_id}).sort("fecha", -1)]


@compras.post("/recepcion-mercancia", status_code=201)
async def crear_recepcion(
    payload: RecepcionCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()
    bodega = await db.bodegas.find_one(
        {"_id": _oid(payload.bodega_id, "bodega_id"), "empresa_id": empresa_id}
    )
    if not bodega:
        raise HTTPException(404, "Bodega no encontrada")

    consecutivo = await db.recepciones_mercancia.count_documents({"empresa_id": empresa_id}) + 1
    referencia = f"REC-{consecutivo}"
    lineas = []
    valor_total = 0.0

    for it in payload.items:
        if it.cantidad <= 0:
            raise HTTPException(422, "La cantidad debe ser mayor a cero")
        prod = await db.productos.find_one(
            {"_id": _oid(it.producto_id, "producto_id"), "empresa_id": empresa_id}
        )
        if not prod:
            raise HTTPException(404, "Producto no encontrado en el catálogo")

        # Entrada a bodega + recálculo de costo promedio ponderado global
        existencia_bodega = await _existencia_por_bodega(db, empresa_id, it.producto_id, payload.bodega_id)
        total_prev = 0.0
        async for d in db.existencias_por_bodega.find(
            {"empresa_id": empresa_id, "producto_id": it.producto_id}
        ):
            total_prev += float(d.get("cantidad", 0))
        costo_actual = float(prod.get("costo_promedio_ponderado", 0))
        nueva_total = total_prev + it.cantidad
        nuevo_costo = (
            ((total_prev * costo_actual) + (it.cantidad * it.costo_unitario)) / nueva_total
            if nueva_total > 0 else it.costo_unitario
        )
        await _set_existencia_por_bodega(
            db, empresa_id, it.producto_id, payload.bodega_id, existencia_bodega + it.cantidad
        )
        await db.productos.update_one(
            {"_id": prod["_id"]}, {"$set": {"costo_promedio_ponderado": round(nuevo_costo, 6)}}
        )
        await db.movimientos_inventario.insert_one({
            "empresa_id": empresa_id,
            "producto_id": it.producto_id,
            "bodega_id": payload.bodega_id,
            "tipo": "entrada",
            "cantidad": it.cantidad,
            "costo_unitario": it.costo_unitario,
            "fecha": payload.fecha,
            "referencia_documento": referencia,
            "fecha_creacion": datetime.now(timezone.utc),
        })
        valor_linea = it.cantidad * it.costo_unitario
        valor_total += valor_linea
        lineas.append({
            "producto_id": it.producto_id,
            "producto_nombre": prod.get("nombre", ""),
            "cantidad": it.cantidad,
            "costo_unitario": it.costo_unitario,
            "valor": round(valor_linea, 2),
        })

    doc = {
        "empresa_id": empresa_id,
        "consecutivo": consecutivo,
        "referencia": referencia,
        "orden_compra_id": payload.orden_compra_id,
        "bodega_id": payload.bodega_id,
        "bodega_nombre": bodega.get("nombre", ""),
        "fecha": payload.fecha,
        "items": lineas,
        "valor_total": round(valor_total, 2),
        "observaciones": payload.observaciones,
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.recepciones_mercancia.insert_one(doc)
    if payload.orden_compra_id:
        await db.ordenes_compra.update_one(
            {"_id": _oid(payload.orden_compra_id, "orden_compra_id"), "empresa_id": empresa_id},
            {"$set": {"estado": "recibida"}},
        )
    return _serialize(await db.recepciones_mercancia.find_one({"_id": res.inserted_id}))


# ---------------------------------------------------------------------------
# Facturas de proveedor + retenciones
# ---------------------------------------------------------------------------

class FacturaProveedorCrear(BaseModel):
    proveedor_id: str
    numero_factura: str
    fecha: str
    fecha_vencimiento: str | None = None
    orden_compra_id: str | None = None
    afecta_inventario: bool = True
    tarifa_retefuente: float = 0
    tarifa_reteica: float = 0
    tarifa_reteiva: float = 0
    observaciones: str | None = None
    items: list[ItemCompra] = Field(min_length=1)


async def _asiento_factura_proveedor(db, empresa_id: str, doc: dict) -> None:
    """Débito compra/inventario + IVA descontable; crédito proveedores y retenciones."""
    ahora = datetime.now(timezone.utc)
    ref = f"FPROV-{doc['numero_factura']}"
    cta_compra = await _cuenta_puc(db, empresa_id, "1435" if doc["afecta_inventario"] else "6205")
    cta_iva_desc = await _cuenta_puc(db, empresa_id, "2408")
    cta_proveedores = await _cuenta_puc(db, empresa_id, "2205")
    ctas_ret = {
        "retefuente": await _cuenta_puc(db, empresa_id, "2365"),
        "reteiva": await _cuenta_puc(db, empresa_id, "2367"),
        "reteica": await _cuenta_puc(db, empresa_id, "2368"),
    }

    def linea(cuenta, debito=0.0, credito=0.0):
        return {
            "empresa_id": empresa_id, "fecha": doc["fecha"], "cuenta_puc_id": cuenta,
            "tercero_id": doc["proveedor_id"], "debito": round(debito, 2),
            "credito": round(credito, 2), "referencia": ref, "fecha_creacion": ahora,
        }

    asientos = []
    if cta_compra:
        asientos.append(linea(cta_compra, debito=doc["subtotal"]))
    if doc["iva_total"] > 0 and cta_iva_desc:
        asientos.append(linea(cta_iva_desc, debito=doc["iva_total"]))
    for clave, cuenta in ctas_ret.items():
        valor = doc["retenciones"].get(clave, 0)
        if valor > 0 and cuenta:
            asientos.append(linea(cuenta, credito=valor))
    if cta_proveedores:
        asientos.append(linea(cta_proveedores, credito=doc["total_a_pagar"]))
    if asientos:
        await db.asientos_contables.insert_many(asientos)


@compras.get("/facturas-proveedor")
async def listar_facturas_proveedor(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.facturas_proveedor.find({"empresa_id": empresa_id}).sort("fecha", -1)]


@compras.post("/facturas-proveedor", status_code=201)
async def crear_factura_proveedor(
    payload: FacturaProveedorCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()
    proveedor = await _proveedor(db, empresa_id, payload.proveedor_id)
    items, subtotal, iva_total, total = _totalizar(payload.items)

    retenciones = {
        "retefuente": round(subtotal * payload.tarifa_retefuente / 100, 2),
        "reteica": round(subtotal * payload.tarifa_reteica / 100, 2),
        "reteiva": round(iva_total * payload.tarifa_reteiva / 100, 2),
    }
    total_retenciones = round(sum(retenciones.values()), 2)
    total_a_pagar = round(total - total_retenciones, 2)

    doc = {
        "empresa_id": empresa_id,
        "proveedor_id": payload.proveedor_id,
        "proveedor_nombre": proveedor.get("nombre", ""),
        "numero_factura": payload.numero_factura,
        "fecha": payload.fecha,
        "fecha_vencimiento": payload.fecha_vencimiento,
        "orden_compra_id": payload.orden_compra_id,
        "afecta_inventario": payload.afecta_inventario,
        "items": items,
        "subtotal": subtotal,
        "iva_total": iva_total,
        "total": total,
        "tarifas": {
            "retefuente": payload.tarifa_retefuente,
            "reteica": payload.tarifa_reteica,
            "reteiva": payload.tarifa_reteiva,
        },
        "retenciones": retenciones,
        "total_retenciones": total_retenciones,
        "total_a_pagar": total_a_pagar,
        "saldo_pendiente": total_a_pagar,
        "estado": "pendiente",
        "observaciones": payload.observaciones,
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.facturas_proveedor.insert_one(doc)
    await _asiento_factura_proveedor(db, empresa_id, doc)
    if payload.orden_compra_id:
        await db.ordenes_compra.update_one(
            {"_id": _oid(payload.orden_compra_id, "orden_compra_id"), "empresa_id": empresa_id},
            {"$set": {"estado": "facturada"}},
        )
    return _serialize(await db.facturas_proveedor.find_one({"_id": res.inserted_id}))


@compras.get("/retenciones")
async def resumen_retenciones(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    """Retenciones practicadas a proveedores dentro del rango."""
    db = get_db()
    filas = []
    totales = {"retefuente": 0.0, "reteica": 0.0, "reteiva": 0.0, "base": 0.0}
    async for f in db.facturas_proveedor.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}}
    ).sort("fecha", 1):
        ret = f.get("retenciones", {})
        filas.append({
            "fecha": f.get("fecha"),
            "proveedor": f.get("proveedor_nombre", ""),
            "documento": f.get("numero_factura", ""),
            "base": f.get("subtotal", 0),
            "retefuente": ret.get("retefuente", 0),
            "reteica": ret.get("reteica", 0),
            "reteiva": ret.get("reteiva", 0),
            "total": f.get("total_retenciones", 0),
        })
        totales["base"] += f.get("subtotal", 0)
        for k in ("retefuente", "reteica", "reteiva"):
            totales[k] += ret.get(k, 0)
    totales = {k: round(v, 2) for k, v in totales.items()}
    totales["total"] = round(totales["retefuente"] + totales["reteica"] + totales["reteiva"], 2)
    return {"periodo": {"desde": desde, "hasta": hasta}, "filas": filas, "resumen": totales}


router.include_router(compras)

# Catálogo de conceptos de retención (tarifas parametrizables por empresa)
router.include_router(
    crud_router(
        prefix="/api/compras/conceptos-retencion",
        coleccion="conceptos_retencion",
        modulo_permiso="compras",
        tags=["compras:retenciones"],
    )
)
