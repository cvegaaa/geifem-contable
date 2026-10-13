"""Compras: orden de compra -> entrada de mercancía -> factura de proveedor.

- La orden de compra no tiene efectos contables; su estado se deriva de las
  entradas y facturas activas que la referencian.
- La entrada de mercancía suma existencias, recalcula el costo promedio y
  contabiliza: débito inventario (cuenta del producto) / crédito "mercancía
  por facturar".
- La factura de proveedor de mercancía cruza "mercancía por facturar" contra
  proveedores (más IVA y retenciones); si es un gasto, debita la cuenta de
  gasto elegida. Todas las cuentas salen de los parámetros contables.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import impuestos, inventario, parametros
from core.auth.dependencies import get_empresa_activa, require_permiso
from core.documentos import (
    NO_ANULADO,
    Linea,
    ahora,
    auditar,
    borrar_asientos,
    campos_conservados,
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
compras = APIRouter(prefix="/api/compras", tags=["compras"])


class Anulacion(BaseModel):
    motivo: str | None = None


class ItemCompra(BaseModel):
    producto_id: str | None = None
    descripcion: str = ""
    cantidad: float = Field(gt=0)
    costo_unitario: float = Field(ge=0)
    tarifa_iva: float = Field(default=0, ge=0, le=100)
    # Concepto de ReteFuente de la línea; si falta, se usa el del producto.
    concepto_retefuente_id: str | None = None


def _totalizar(items: list[ItemCompra]) -> tuple[list[dict], float, float, float]:
    calc, subtotal, iva_total = [], 0.0, 0.0
    for it in items:
        ls = it.cantidad * it.costo_unitario
        li = ls * it.tarifa_iva / 100
        calc.append({**it.model_dump(), "subtotal": redondear(ls, 2), "iva": redondear(li, 2),
                     "total": redondear(ls + li, 2)})
        subtotal += ls
        iva_total += li
    return calc, redondear(subtotal, 2), redondear(iva_total, 2), redondear(subtotal + iva_total, 2)


async def _proveedor(empresa_id: str, proveedor_id: str, s) -> dict:
    doc = await get_db().terceros.find_one(
        {"_id": oid(proveedor_id, "proveedor_id"), "empresa_id": empresa_id}, session=s
    )
    if not doc:
        raise HTTPException(404, "Proveedor no encontrado")
    return doc


async def _actualizar_estado_orden(empresa_id: str, orden_id: str | None, s) -> None:
    """abierta -> recibida -> facturada, según los documentos activos que la usan."""
    if not orden_id:
        return
    db = get_db()
    filtro = {"empresa_id": empresa_id, "orden_compra_id": orden_id, **NO_ANULADO}
    if await db.facturas_proveedor.find_one(filtro, session=s):
        estado = "facturada"
    elif await db.recepciones_mercancia.find_one(filtro, session=s):
        estado = "recibida"
    else:
        estado = "abierta"
    await db.ordenes_compra.update_one(
        {"_id": oid(orden_id, "orden_compra_id"), "empresa_id": empresa_id, **NO_ANULADO},
        {"$set": {"estado": estado}},
        session=s,
    )


async def _validar_orden(empresa_id: str, orden_id: str | None, s) -> None:
    if orden_id and not await get_db().ordenes_compra.find_one(
        {"_id": oid(orden_id, "orden_compra_id"), "empresa_id": empresa_id, **NO_ANULADO}, session=s
    ):
        raise HTTPException(404, "Orden de compra no encontrada o anulada")


# ---------------------------------------------------------------------------
# Órdenes de compra
# ---------------------------------------------------------------------------

class OrdenCompraCrear(BaseModel):
    proveedor_id: str
    fecha: str
    bodega_id: str | None = None
    observaciones: str | None = None
    items: list[ItemCompra] = Field(min_length=1)


async def _armar_orden(empresa_id: str, payload: OrdenCompraCrear, s) -> dict:
    proveedor = await _proveedor(empresa_id, payload.proveedor_id, s)
    items, subtotal, iva_total, total = _totalizar(payload.items)
    return {**payload.model_dump(exclude={"items"}), "proveedor_nombre": proveedor.get("nombre", ""),
            "items": items, "subtotal": subtotal, "iva_total": iva_total, "total": total}


@compras.get("/ordenes-compra")
async def listar_ordenes(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    cursor = get_db().ordenes_compra.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@compras.post("/ordenes-compra", status_code=201)
async def crear_orden(
    payload: OrdenCompraCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_orden(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "orden_compra", s)
        doc.update({"empresa_id": empresa_id, "prefijo": "OC", "consecutivo": consecutivo,
                    "numero": formatear_numero("OC", consecutivo), "estado": "abierta",
                    "creado_por": usuario["id"], "fecha_creacion": ahora()})
        res = await db.ordenes_compra.insert_one(doc, session=s)
        await auditar(empresa_id, "orden_compra", str(res.inserted_id), doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.ordenes_compra.find_one({"_id": nuevo}))


@compras.get("/ordenes-compra/{oc_id}")
async def obtener_orden(
    oc_id: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    doc = await get_db().ordenes_compra.find_one({"_id": oid(oc_id), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Orden no encontrada")
    return serializar(doc)


@compras.put("/ordenes-compra/{oc_id}")
async def editar_orden(
    oc_id: str,
    payload: OrdenCompraCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("ordenes_compra", empresa_id, oc_id, s)
        if existente.get("estado") != "abierta":
            raise HTTPException(409, "Solo se pueden editar órdenes abiertas (sin entradas ni facturas)")
        doc = await _armar_orden(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "estado": "abierta",
                    "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.ordenes_compra.replace_one({"_id": existente["_id"]}, doc, session=s)
        await auditar(empresa_id, "orden_compra", oc_id, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.ordenes_compra.find_one({"_id": oid(oc_id)}))


@compras.post("/ordenes-compra/{oc_id}/anular")
async def anular_orden(
    oc_id: str,
    payload: Anulacion | None = None,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "inactivar")),
):
    db = get_db()
    motivo = payload.motivo if payload else None

    async def _tx(s):
        existente = await cargar_editable("ordenes_compra", empresa_id, oc_id, s)
        if existente.get("estado") != "abierta":
            raise HTTPException(409, "Solo se pueden anular órdenes abiertas: anula primero sus entradas y facturas")
        await db.ordenes_compra.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], motivo)}, session=s
        )
        await auditar(empresa_id, "orden_compra", oc_id, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": motivo})

    await en_transaccion(_tx)
    return serializar(await db.ordenes_compra.find_one({"_id": oid(oc_id)}))


# ---------------------------------------------------------------------------
# Entrada de mercancía (suma existencias y recalcula el costo promedio)
# ---------------------------------------------------------------------------

class ItemRecepcion(BaseModel):
    producto_id: str
    cantidad: float = Field(gt=0)
    costo_unitario: float = Field(ge=0)


class RecepcionCrear(BaseModel):
    orden_compra_id: str | None = None
    bodega_id: str
    fecha: str
    observaciones: str | None = None
    items: list[ItemRecepcion] = Field(min_length=1)


RECEPCION = "recepcion"


async def _armar_recepcion(empresa_id: str, payload: RecepcionCrear, s) -> dict:
    db = get_db()
    bodega = await db.bodegas.find_one(
        {"_id": oid(payload.bodega_id, "bodega_id"), "empresa_id": empresa_id}, session=s
    )
    if not bodega:
        raise HTTPException(404, "Bodega no encontrada")
    await _validar_orden(empresa_id, payload.orden_compra_id, s)
    lineas, valor_total = [], 0.0
    for it in payload.items:
        prod = await db.productos.find_one(
            {"_id": oid(it.producto_id, "producto_id"), "empresa_id": empresa_id}, session=s
        )
        if not prod:
            raise HTTPException(404, "Producto no encontrado en el catálogo")
        valor = it.cantidad * it.costo_unitario
        valor_total += valor
        lineas.append({**it.model_dump(), "producto_nombre": prod.get("nombre", ""), "valor": redondear(valor, 2)})
    return {**payload.model_dump(exclude={"items"}), "bodega_nombre": bodega.get("nombre", ""),
            "items": lineas, "valor_total": redondear(valor_total, 2), "estado": "registrada"}


async def _aplicar_recepcion(empresa_id: str, rid: str, doc: dict, s) -> None:
    db = get_db()
    params = await parametros.obtener(empresa_id, s)
    por_cuenta: dict[str, float] = {}
    for it in doc["items"]:
        prod = await db.productos.find_one({"_id": oid(it["producto_id"]), "empresa_id": empresa_id}, session=s)
        cuenta = parametros.cuenta_producto(prod, "cuenta_inventario", params)
        por_cuenta[cuenta] = por_cuenta.get(cuenta, 0.0) + it["valor"]
    lineas = [Linea(codigo=c, debito=v) for c, v in por_cuenta.items()]
    lineas.append(Linea(codigo=params["inventario_por_facturar"], credito=doc["valor_total"],
                        descripcion="Mercancía recibida por facturar"))
    await registrar_asientos(empresa_id, RECEPCION, rid, doc["numero"], doc["fecha"], lineas, s)
    await inventario.registrar_movimientos(
        empresa_id, RECEPCION, rid, doc["numero"], doc["fecha"],
        [{"producto_id": it["producto_id"], "bodega_id": doc["bodega_id"], "tipo": "entrada",
          "cantidad": it["cantidad"], "costo_unitario": it["costo_unitario"]} for it in doc["items"]],
        s,
    )
    await _actualizar_estado_orden(empresa_id, doc.get("orden_compra_id"), s)


@compras.get("/recepcion-mercancia")
async def listar_recepciones(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    cursor = get_db().recepciones_mercancia.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@compras.post("/recepcion-mercancia", status_code=201)
async def crear_recepcion(
    payload: RecepcionCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_recepcion(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "recepcion", s)
        doc.update({"empresa_id": empresa_id, "prefijo": "EM", "consecutivo": consecutivo,
                    "numero": formatear_numero("EM", consecutivo),
                    "creado_por": usuario["id"], "fecha_creacion": ahora()})
        res = await db.recepciones_mercancia.insert_one(doc, session=s)
        rid = str(res.inserted_id)
        await _aplicar_recepcion(empresa_id, rid, doc, s)
        await auditar(empresa_id, RECEPCION, rid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.recepciones_mercancia.find_one({"_id": nuevo}))


@compras.put("/recepcion-mercancia/{rid}")
async def editar_recepcion(
    rid: str,
    payload: RecepcionCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("recepciones_mercancia", empresa_id, rid, s)
        await borrar_asientos(empresa_id, RECEPCION, rid, s)
        previos = await inventario.borrar_movimientos(empresa_id, RECEPCION, rid, s, recalcular_despues=False)
        doc = await _armar_recepcion(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.recepciones_mercancia.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar_recepcion(empresa_id, rid, doc, s)
        await inventario.recalcular(empresa_id, previos, s)
        if existente.get("orden_compra_id") != doc.get("orden_compra_id"):
            await _actualizar_estado_orden(empresa_id, existente.get("orden_compra_id"), s)
        await auditar(empresa_id, RECEPCION, rid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.recepciones_mercancia.find_one({"_id": oid(rid)}))


@compras.post("/recepcion-mercancia/{rid}/anular")
async def anular_recepcion(
    rid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("recepciones_mercancia", empresa_id, rid, s)
        # Si ya se vendió esa mercancía, el recálculo lo detecta y rechaza la anulación.
        await borrar_asientos(empresa_id, RECEPCION, rid, s)
        await inventario.borrar_movimientos(empresa_id, RECEPCION, rid, s)
        await db.recepciones_mercancia.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await _actualizar_estado_orden(empresa_id, existente.get("orden_compra_id"), s)
        await auditar(empresa_id, RECEPCION, rid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.recepciones_mercancia.find_one({"_id": oid(rid)}))


# ---------------------------------------------------------------------------
# Facturas de proveedor + retenciones
# ---------------------------------------------------------------------------

class FacturaProveedorCrear(BaseModel):
    proveedor_id: str
    numero_factura: str = Field(min_length=1)
    fecha: str
    fecha_vencimiento: str | None = None
    orden_compra_id: str | None = None
    afecta_inventario: bool = True
    # Cuenta de gasto/costo cuando la compra no es de mercancía (p. ej. 5135 servicios).
    # Vacía = la de los parámetros contables.
    cuenta_gasto: str | None = None
    # Las retenciones se calculan solas según el perfil de la empresa, el del
    # proveedor y los conceptos de cada línea; aquí solo se elige lo que depende del documento.
    concepto_reteica_id: str | None = None
    aplicar_reteiva: bool = True
    observaciones: str | None = None
    items: list[ItemCompra] = Field(min_length=1)


FACT_PROV = "factura_proveedor"


async def _armar_factura_proveedor(
    empresa_id: str, payload: FacturaProveedorCrear, s, excluir_id=None, verificar_duplicada: bool = True
) -> dict:
    db = get_db()
    proveedor = await _proveedor(empresa_id, payload.proveedor_id, s)
    await _validar_orden(empresa_id, payload.orden_compra_id, s)
    if verificar_duplicada:
        duplicada = {"empresa_id": empresa_id, "proveedor_id": payload.proveedor_id,
                     "numero_factura": payload.numero_factura, **NO_ANULADO}
        if excluir_id is not None:
            duplicada["_id"] = {"$ne": excluir_id}
        if await db.facturas_proveedor.find_one(duplicada, session=s):
            raise HTTPException(409, f"Ya registraste la factura {payload.numero_factura} de este proveedor")

    _, cap = await impuestos.empresa_y_capacidades(empresa_id, s)
    if not cap["cobra_iva"]:
        # No responsable de IVA: el IVA pagado no es descontable, se suma al costo o gasto.
        for it in payload.items:
            it.costo_unitario = redondear(it.costo_unitario * (1 + it.tarifa_iva / 100), 6)
            it.tarifa_iva = 0
    items, subtotal, iva_total, total = _totalizar(payload.items)

    # Conceptos de ReteFuente por línea (el de la línea o el del producto).
    conceptos: dict[str, dict] = {}
    for src, it in zip(payload.items, items):
        cid = src.concepto_retefuente_id
        if not cid and src.producto_id:
            prod = await db.productos.find_one(
                {"_id": oid(src.producto_id, "producto_id"), "empresa_id": empresa_id}, session=s)
            cid = (prod or {}).get("concepto_retefuente_compra_id")
        if cid:
            if cid not in conceptos:
                conceptos[cid] = await impuestos.validar_concepto(empresa_id, cid, "retefuente", "Concepto de retención")
            it["concepto_retefuente_id"] = cid
    concepto_ica = await impuestos.validar_concepto(empresa_id, payload.concepto_reteica_id, "reteica", "ReteICA")
    calculo = impuestos.retenciones_compra(
        cap, proveedor,
        [{"subtotal": it["subtotal"], "concepto": conceptos.get(it.get("concepto_retefuente_id"))} for it in items],
        concepto_ica, payload.aplicar_reteiva, iva_total, payload.fecha,
    )
    total_a_pagar = redondear(total - calculo["total"], 2)
    return {
        **payload.model_dump(exclude={"items"}),
        "proveedor_nombre": proveedor.get("nombre", ""),
        "items": items, "subtotal": subtotal, "iva_total": iva_total, "total": total,
        "iva_descontable": cap["cobra_iva"],
        "retenciones": calculo["retenciones"],
        "detalle_retenciones": calculo["detalle"],
        "uvt_aplicada": calculo["uvt"],
        "total_retenciones": calculo["total"],
        "total_a_pagar": total_a_pagar,
        "saldo_pendiente": total_a_pagar,
        "estado": "pendiente",
    }


async def _aplicar_factura_proveedor(empresa_id: str, fid: str, doc: dict, s) -> None:
    t = doc["proveedor_id"]
    p = await parametros.obtener(empresa_id, s)
    # Mercancía: cruza lo que la entrada dejó en "por facturar". Gasto: cuenta elegida.
    cuenta_compra = p["inventario_por_facturar"] if doc["afecta_inventario"] else doc.get("cuenta_gasto") or p["gasto_compras"]
    doc["cuenta_cxp"] = p["proveedores"]
    await get_db().facturas_proveedor.update_one(
        {"_id": oid(fid)}, {"$set": {"cuenta_cxp": doc["cuenta_cxp"]}}, session=s
    )
    lineas = [
        Linea(codigo=cuenta_compra, debito=doc["subtotal"], tercero_id=t),
        Linea(codigo=p["iva_descontable"], debito=doc["iva_total"] if doc.get("iva_descontable", True) else 0,
              tercero_id=t, descripcion="IVA descontable"),
        Linea(codigo=doc["cuenta_cxp"], credito=doc["total_a_pagar"], tercero_id=t),
    ]
    for cuenta, valor in impuestos.lineas_retencion(doc.get("detalle_retenciones") or [], p, "practicada"):
        lineas.append(Linea(codigo=cuenta, credito=valor, tercero_id=t, descripcion="Retención practicada"))
    await registrar_asientos(empresa_id, FACT_PROV, fid, doc["numero"], doc["fecha"], lineas, s)
    await _actualizar_estado_orden(empresa_id, doc.get("orden_compra_id"), s)


async def _validar_sin_pagos(empresa_id: str, fid: str, s) -> None:
    if await get_db().pagos.find_one({"empresa_id": empresa_id, "documento_id": fid, **NO_ANULADO}, session=s):
        raise HTTPException(409, "La factura tiene pagos registrados: anúlalos primero")


@compras.post("/facturas-proveedor/previsualizar")
async def previsualizar_factura_proveedor(
    payload: FacturaProveedorCrear,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    """Calcula totales y retenciones sin guardar (lo usa el formulario en vivo)."""
    doc = await _armar_factura_proveedor(empresa_id, payload, None, verificar_duplicada=False)
    return {k: doc[k] for k in ("subtotal", "iva_total", "total", "retenciones", "detalle_retenciones",
                                "total_retenciones", "total_a_pagar", "iva_descontable")}


@compras.get("/facturas-proveedor")
async def listar_facturas_proveedor(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    cursor = get_db().facturas_proveedor.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@compras.post("/facturas-proveedor", status_code=201)
async def crear_factura_proveedor(
    payload: FacturaProveedorCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_factura_proveedor(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "factura_proveedor", s)
        doc.update({"empresa_id": empresa_id, "prefijo": "FP", "consecutivo": consecutivo,
                    "numero": formatear_numero("FP", consecutivo),
                    "creado_por": usuario["id"], "fecha_creacion": ahora()})
        res = await db.facturas_proveedor.insert_one(doc, session=s)
        fid = str(res.inserted_id)
        await _aplicar_factura_proveedor(empresa_id, fid, doc, s)
        await auditar(empresa_id, FACT_PROV, fid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.facturas_proveedor.find_one({"_id": nuevo}))


@compras.put("/facturas-proveedor/{fid}")
async def editar_factura_proveedor(
    fid: str,
    payload: FacturaProveedorCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("facturas_proveedor", empresa_id, fid, s)
        await _validar_sin_pagos(empresa_id, fid, s)
        await borrar_asientos(empresa_id, FACT_PROV, fid, s)
        doc = await _armar_factura_proveedor(empresa_id, payload, s, excluir_id=existente["_id"])
        doc.update({**campos_conservados(existente), "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.facturas_proveedor.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar_factura_proveedor(empresa_id, fid, doc, s)
        if existente.get("orden_compra_id") != doc.get("orden_compra_id"):
            await _actualizar_estado_orden(empresa_id, existente.get("orden_compra_id"), s)
        await auditar(empresa_id, FACT_PROV, fid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.facturas_proveedor.find_one({"_id": oid(fid)}))


@compras.post("/facturas-proveedor/{fid}/anular")
async def anular_factura_proveedor(
    fid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("facturas_proveedor", empresa_id, fid, s)
        await _validar_sin_pagos(empresa_id, fid, s)
        await borrar_asientos(empresa_id, FACT_PROV, fid, s)
        await db.facturas_proveedor.update_one(
            {"_id": existente["_id"]},
            {"$set": {**marca_anulacion(usuario["id"], payload.motivo), "saldo_pendiente": 0}},
            session=s,
        )
        await _actualizar_estado_orden(empresa_id, existente.get("orden_compra_id"), s)
        await auditar(empresa_id, FACT_PROV, fid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.facturas_proveedor.find_one({"_id": oid(fid)}))


@compras.get("/retenciones")
async def resumen_retenciones(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    """Retenciones practicadas a proveedores dentro del rango."""
    filas = []
    totales = {"retefuente": 0.0, "reteica": 0.0, "reteiva": 0.0, "base": 0.0}
    async for f in get_db().facturas_proveedor.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}, **NO_ANULADO}
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
    totales = {k: redondear(v, 2) for k, v in totales.items()}
    totales["total"] = redondear(totales["retefuente"] + totales["reteica"] + totales["reteiva"], 2)
    return {"periodo": {"desde": desde, "hasta": hasta}, "filas": filas, "resumen": totales}


router.include_router(compras)
