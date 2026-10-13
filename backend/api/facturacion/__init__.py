"""Facturación: factura de venta, documento POS y notas crédito/débito.

Cada documento se numera solo, contabiliza en el libro y, si vende
productos inventariables, descuenta existencias y registra el costo de
venta (6135 / 1435) al costo promedio vigente.

La emisión electrónica ante la DIAN se hará vía Alegra (Fase 2). Mientras
`estado_dian` sea `borrador`, el documento se puede editar o anular.
"""
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth.dependencies import get_empresa_activa, require_permiso
from core.dian.cliente_pt import get_cliente_pt
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
from core import impuestos, inventario, parametros
from db import get_db
from core.dinero import redondear

router = APIRouter(prefix="/api/facturacion", tags=["facturacion"])


class Anulacion(BaseModel):
    motivo: str | None = None


# ---------------------------------------------------------------------------
# Cálculos y efectos compartidos
# ---------------------------------------------------------------------------

class ItemVenta(BaseModel):
    producto_id: str | None = None
    descripcion: str | None = None
    cantidad: float = Field(gt=0)
    precio_unitario: float = Field(ge=0)
    tarifa_iva: float = Field(default=0, ge=0, le=100)


async def _totalizar(
    empresa_id: str, items: list[ItemVenta], s, cap: dict | None = None
) -> tuple[list[dict], float, float, float]:
    """Totales por línea: subtotal, IVA e impuesto al consumo.

    El IVA lo gobiernan el perfil de la empresa y el tipo de IVA del producto; el
    impuesto al consumo (INC) lo define el producto y se causa en la cuenta de ese impuesto.
    """
    db = get_db()
    if cap is None:
        _, cap = await impuestos.empresa_y_capacidades(empresa_id, s)
    calc, subtotal, iva_total, inc_total = [], 0.0, 0.0, 0.0
    tasas_inc: dict[str, dict] = {}
    for it in items:
        producto = None
        if it.producto_id:
            producto = await db.productos.find_one(
                {"_id": oid(it.producto_id, "producto_id"), "empresa_id": empresa_id}, session=s
            )
            if not producto:
                raise HTTPException(404, "Producto no encontrado en el catálogo")
        elif not (it.descripcion or "").strip():
            raise HTTPException(422, "Cada ítem necesita un producto o una descripción")
        tarifa = it.tarifa_iva
        if not cap["cobra_iva"] or (producto and producto.get("tipo_iva", "gravado") != "gravado"):
            tarifa = 0.0  # no responsable de IVA, o producto excluido/exento
        ls = it.cantidad * it.precio_unitario
        li = ls * tarifa / 100
        inc, cuenta_inc = 0.0, None
        inc_id = (producto or {}).get("impuesto_consumo_id")
        if inc_id:
            if inc_id not in tasas_inc:
                tasas_inc[inc_id] = await db.impuestos_config.find_one(
                    {"_id": oid(inc_id), "empresa_id": empresa_id, "tipo": "INC", "activo": {"$ne": False}}, session=s)
            tasa = tasas_inc[inc_id]
            if not tasa or not tasa.get("cuenta_contable"):
                raise HTTPException(409, f"El impuesto al consumo de «{producto.get('nombre')}» no está configurado")
            inc = redondear(ls * float(tasa["tarifa"]) / 100, 2)
            cuenta_inc = tasa["cuenta_contable"]
        calc.append({
            **it.model_dump(),
            "tarifa_iva": tarifa,
            "inc": inc, "cuenta_inc": cuenta_inc,
            "descripcion": it.descripcion or (producto or {}).get("nombre", ""),
            "inventariable": bool(producto) and producto.get("inventariable", True) is not False,
            "concepto_retefuente_id": (producto or {}).get("concepto_retefuente_venta_id"),
            "aplica_reteica": (producto or {}).get("aplica_reteica", True) is not False,
            "subtotal": redondear(ls, 2), "iva": redondear(li, 2), "total": redondear(ls + li + inc, 2),
        })
        subtotal += ls
        iva_total += li
        inc_total += inc
    return calc, redondear(subtotal, 2), redondear(iva_total, 2), redondear(inc_total, 2)


async def _efectos_venta(
    empresa_id: str, doc_tipo: str, doc_id: str, doc: dict, cuenta_debito: str, s
) -> None:
    """Salida de inventario + asiento de venta y de costo.

    Ingreso, costo e inventario usan las cuentas propias de cada producto o,
    si no las tiene, las de los parámetros contables de la empresa.
    """
    db = get_db()
    params = await parametros.obtener(empresa_id, s)
    bodega_id = doc.get("bodega_id") or await inventario.bodega_principal(empresa_id, s)

    productos: dict[str, dict] = {}
    for it in doc["items"]:
        if it.get("producto_id") and it["producto_id"] not in productos:
            productos[it["producto_id"]] = await db.productos.find_one(
                {"_id": oid(it["producto_id"]), "empresa_id": empresa_id}, session=s
            )

    ingresos: dict[str, float] = defaultdict(float)
    costos: dict[tuple[str, str], float] = defaultdict(float)  # (cuenta costo, cuenta inventario)
    for it in doc["items"]:
        prod = productos.get(it.get("producto_id"))
        ingresos[parametros.cuenta_producto(prod, "cuenta_ingreso", params)] += it["subtotal"]
        if it.get("inventariable"):
            costo = it["cantidad"] * await inventario.costo_promedio(empresa_id, it["producto_id"], s)
            clave = (parametros.cuenta_producto(prod, "cuenta_costo", params),
                     parametros.cuenta_producto(prod, "cuenta_inventario", params))
            costos[clave] += costo

    await inventario.registrar_movimientos(
        empresa_id, doc_tipo, doc_id, doc["numero"], doc["fecha"],
        [{"producto_id": it["producto_id"], "bodega_id": bodega_id, "tipo": "salida",
          "cantidad": it["cantidad"]} for it in doc["items"] if it.get("inventariable")],
        s,
    )

    tercero = doc.get("cliente_id")
    ret = doc.get("retenciones") or {}
    neto = redondear(doc["total"] - sum(ret.values()), 2)
    lineas = [Linea(codigo=cuenta_debito, debito=neto, tercero_id=tercero)]
    for cuenta, valor in impuestos.lineas_retencion(doc.get("detalle_retenciones") or [], params, "sufrida"):
        lineas.append(Linea(codigo=cuenta, debito=valor, tercero_id=tercero, descripcion="Retención practicada por el cliente"))
    lineas += [Linea(codigo=c, credito=v, tercero_id=tercero) for c, v in ingresos.items()]
    lineas.append(Linea(codigo=params["iva_generado"], credito=doc["iva_total"], tercero_id=tercero))
    inc_por_cuenta: dict[str, float] = defaultdict(float)
    for it in doc["items"]:
        if it.get("inc"):
            inc_por_cuenta[it["cuenta_inc"]] += it["inc"]
    for cuenta, valor in inc_por_cuenta.items():
        lineas.append(Linea(codigo=cuenta, credito=redondear(valor, 2), tercero_id=tercero, descripcion="Impuesto al consumo"))
    autorret = doc.get("autorretencion") or 0
    if autorret:
        lineas.append(Linea(codigo=params["autorretencion_anticipo"], debito=autorret, descripcion="Autorretención de renta"))
        lineas.append(Linea(codigo=params["autorretencion_pasivo"], credito=autorret, descripcion="Autorretención de renta"))
    for (cuenta_costo, cuenta_inv), valor in costos.items():
        lineas.append(Linea(codigo=cuenta_costo, debito=valor, descripcion="Costo de venta"))
        lineas.append(Linea(codigo=cuenta_inv, credito=valor, descripcion="Costo de venta"))
    await registrar_asientos(empresa_id, doc_tipo, doc_id, doc["numero"], doc["fecha"], lineas, s)


async def _revertir(empresa_id: str, doc_tipo: str, doc_id: str, s, recalcular: bool = True) -> None:
    await borrar_asientos(empresa_id, doc_tipo, doc_id, s)
    await inventario.borrar_movimientos(empresa_id, doc_tipo, doc_id, s, recalcular)


async def _cliente(empresa_id: str, cliente_id: str | None, s, obligatorio: bool) -> dict | None:
    if not cliente_id:
        if obligatorio:
            raise HTTPException(422, "Selecciona un cliente")
        return None
    cliente = await get_db().terceros.find_one(
        {"_id": oid(cliente_id, "cliente_id"), "empresa_id": empresa_id, "activo": {"$ne": False}},
        session=s,
    )
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return cliente


# ---------------------------------------------------------------------------
# Factura de venta
# ---------------------------------------------------------------------------

class FacturaCrear(BaseModel):
    cliente_id: str
    resolucion_id: str
    fecha: str
    fecha_vencimiento: str | None = None
    forma_pago_id: str | None = None
    bodega_id: str | None = None
    items: list[ItemVenta] = Field(min_length=1)
    observaciones: str | None = None


FACTURA = "factura"


async def _numerar_factura(empresa_id: str, resolucion_id: str, fecha: str, s) -> tuple[str, int]:
    db = get_db()
    res = await db.resoluciones_dian.find_one(
        {"_id": oid(resolucion_id, "resolucion_id"), "empresa_id": empresa_id, "activo": {"$ne": False}},
        session=s,
    )
    if not res:
        raise HTTPException(404, "Resolución DIAN no encontrada o inactiva")
    if res.get("fecha_inicio") and fecha < str(res["fecha_inicio"]):
        raise HTTPException(409, "La fecha de la factura es anterior a la vigencia de la resolución")
    if res.get("fecha_fin") and fecha > str(res["fecha_fin"]):
        raise HTTPException(409, "La resolución DIAN está vencida para esa fecha")
    try:
        desde, hasta = int(res["rango_desde"]), int(res["rango_hasta"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(409, "La resolución no tiene un rango de numeración válido")
    siguiente = int(res.get("consecutivo_actual") or desde - 1) + 1
    if siguiente > hasta:
        raise HTTPException(409, "Rango de numeración DIAN agotado para esta resolución")
    # Dentro de la transacción: dos facturas simultáneas generan conflicto y una se reintenta.
    await db.resoluciones_dian.update_one(
        {"_id": res["_id"]}, {"$set": {"consecutivo_actual": siguiente}}, session=s
    )
    return str(res.get("prefijo") or ""), siguiente


async def _armar_factura(empresa_id: str, payload: FacturaCrear, s) -> dict:
    cliente = await _cliente(empresa_id, payload.cliente_id, s, obligatorio=True)
    if any(not it.producto_id for it in payload.items):
        raise HTTPException(422, "Cada ítem de la factura debe tener un producto del catálogo")
    _, cap = await impuestos.empresa_y_capacidades(empresa_id, s)
    items, subtotal, iva_total, inc_total = await _totalizar(empresa_id, payload.items, s, cap)
    total = redondear(subtotal + iva_total + inc_total, 2)

    conceptos = {}
    for it in items:
        cid = it.get("concepto_retefuente_id")
        if cid and cid not in conceptos:
            conceptos[cid] = await get_db().conceptos_retencion.find_one(
                {"_id": oid(cid), "empresa_id": empresa_id}, session=s)
    calculo = impuestos.retenciones_venta(
        cap, cliente,
        [{"subtotal": it["subtotal"], "concepto": conceptos.get(it.get("concepto_retefuente_id")),
          "aplica_reteica": it["aplica_reteica"]} for it in items],
        iva_total, payload.fecha,
    )
    neto = redondear(total - calculo["total"], 2)
    return {
        **payload.model_dump(exclude={"items"}),
        "cliente_nombre": cliente.get("nombre", ""),
        "items": items,
        "subtotal": subtotal,
        "iva_total": iva_total,
        "inc_total": inc_total,
        "total": total,
        "retenciones": calculo["retenciones"],
        "detalle_retenciones": calculo["detalle"],
        "total_retenciones": calculo["total"],
        "autorretencion": impuestos.autorretencion(cap, subtotal),
        "total_a_cobrar": neto,
        "saldo_pendiente": neto,
        "estado": "emitida",
        "estado_dian": "borrador",
        "cufe": None,
    }


async def _validar_factura_modificable(empresa_id: str, factura: dict, s) -> None:
    if factura.get("estado_dian", "borrador") != "borrador":
        raise HTTPException(409, "La factura ya fue enviada a la DIAN: corrígela con una nota crédito")
    db = get_db()
    fid = str(factura["_id"])
    if await db.pagos.find_one({"empresa_id": empresa_id, "documento_id": fid, **NO_ANULADO}, session=s):
        raise HTTPException(409, "La factura tiene pagos registrados: anúlalos primero")
    if await db.notas_credito_debito.find_one(
        {"empresa_id": empresa_id, "factura_id": fid, **NO_ANULADO}, session=s
    ):
        raise HTTPException(409, "La factura tiene notas crédito/débito: anúlalas primero")


@router.get("/facturas")
async def listar_facturas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    cursor = get_db().facturas.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/facturas", status_code=201)
async def crear_factura(
    payload: FacturaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_factura(empresa_id, payload, s)
        prefijo, consecutivo = await _numerar_factura(empresa_id, payload.resolucion_id, payload.fecha, s)
        doc.update({
            "empresa_id": empresa_id, "prefijo": prefijo, "consecutivo": consecutivo,
            "numero": f"{prefijo}{consecutivo}", "creado_por": usuario["id"], "fecha_creacion": ahora(),
            "cuenta_cxc": (await parametros.obtener(empresa_id, s))["clientes"],
        })
        res = await db.facturas.insert_one(doc, session=s)
        fid = str(res.inserted_id)
        await _efectos_venta(empresa_id, FACTURA, fid, doc, doc["cuenta_cxc"], s)
        await auditar(empresa_id, FACTURA, fid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.facturas.find_one({"_id": nuevo}))


@router.get("/facturas/{fid}")
async def obtener_factura(
    fid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    doc = await get_db().facturas.find_one({"_id": oid(fid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Factura no encontrada")
    return serializar(doc)


@router.put("/facturas/{fid}")
async def editar_factura(
    fid: str,
    payload: FacturaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("facturas", empresa_id, fid, s)
        await _validar_factura_modificable(empresa_id, existente, s)
        if payload.resolucion_id != existente.get("resolucion_id"):
            raise HTTPException(409, "No se puede cambiar la resolución de una factura ya numerada")
        await _revertir(empresa_id, FACTURA, fid, s, recalcular=False)
        doc = await _armar_factura(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "editado_por": usuario["id"], "fecha_actualizacion": ahora(),
                    "cuenta_cxc": (await parametros.obtener(empresa_id, s))["clientes"]})
        await db.facturas.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _efectos_venta(empresa_id, FACTURA, fid, doc, doc["cuenta_cxc"], s)
        await _recalcular_items_previos(empresa_id, existente, s)
        await auditar(empresa_id, FACTURA, fid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.facturas.find_one({"_id": oid(fid)}))


async def _recalcular_items_previos(empresa_id: str, existente: dict, s) -> None:
    """Si la edición quitó productos, su kardex también debe recalcularse."""
    previos = {it["producto_id"] for it in existente.get("items", []) if it.get("producto_id")}
    if previos:
        await inventario.recalcular(empresa_id, previos, s)


@router.post("/facturas/{fid}/anular")
async def anular_factura(
    fid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("facturas", empresa_id, fid, s)
        await _validar_factura_modificable(empresa_id, existente, s)
        await _revertir(empresa_id, FACTURA, fid, s)
        await db.facturas.update_one(
            {"_id": existente["_id"]},
            {"$set": {**marca_anulacion(usuario["id"], payload.motivo), "saldo_pendiente": 0}},
            session=s,
        )
        await auditar(empresa_id, FACTURA, fid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.facturas.find_one({"_id": oid(fid)}))


@router.post("/facturas/{fid}/enviar-dian")
async def enviar_dian(
    fid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "editar")),
):
    """Emisión electrónica: se conectará con Alegra en la Fase 2."""
    db = get_db()
    factura = await cargar_editable("facturas", empresa_id, fid)
    try:
        resultado = await get_cliente_pt().enviar_factura(empresa_id, factura)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))
    await db.facturas.update_one({"_id": factura["_id"]}, {"$set": resultado})
    return {"ok": True, **resultado}


# ---------------------------------------------------------------------------
# Documento equivalente POS (venta de contado: entra a Caja)
# ---------------------------------------------------------------------------

class PosCrear(BaseModel):
    fecha: str
    caja_id: str | None = None  # si no se indica, la primera caja activa
    cliente_id: str | None = None
    forma_pago_id: str | None = None
    bodega_id: str | None = None
    items: list[ItemVenta] = Field(min_length=1)
    observaciones: str | None = None


POS = "pos"


async def _caja_pos(empresa_id: str, caja_id: str | None, s) -> dict:
    db = get_db()
    filtro = {"empresa_id": empresa_id, "activo": {"$ne": False}}
    if caja_id:
        filtro["_id"] = oid(caja_id, "caja_id")
    caja = await db.cajas.find_one(filtro, session=s)
    if not caja:
        raise HTTPException(409, "Crea primero una caja en Tesorería › Caja para registrar ventas POS")
    return caja


async def _efectos_pos(empresa_id: str, did: str, doc: dict, usuario_id: str, s) -> None:
    """Venta de contado: entra a la caja (movimiento de tesorería) y se contabiliza contra su cuenta."""
    from api.tesoreria import cuenta_contable_de

    caja = await _caja_pos(empresa_id, doc.get("caja_id"), s)
    cuenta_caja = await cuenta_contable_de(empresa_id, "caja", caja, s)
    await get_db().movimientos_tesoreria.insert_one({
        "empresa_id": empresa_id, "cuenta_tipo": "caja", "cuenta_id": str(caja["_id"]),
        "cuenta_nombre": caja.get("nombre", ""), "cuenta_contable": cuenta_caja,
        "tipo": "ingreso", "fecha": doc["fecha"], "valor": doc["total"],
        "concepto": "Venta " + doc["numero"], "tercero_id": doc.get("cliente_id"),
        "numero": doc["numero"], "referencia": doc["numero"], "origen": "pos", "estado": "registrado",
        "documento_tipo": POS, "documento_id": did, "creado_por": usuario_id, "fecha_creacion": ahora(),
    }, session=s)
    await _efectos_venta(empresa_id, POS, did, doc, cuenta_caja, s)


async def _revertir_pos(empresa_id: str, did: str, s, recalcular: bool = True) -> None:
    await get_db().movimientos_tesoreria.delete_many(
        {"empresa_id": empresa_id, "documento_tipo": POS, "documento_id": did}, session=s
    )
    await _revertir(empresa_id, POS, did, s, recalcular)


async def _armar_pos(empresa_id: str, payload: PosCrear, s) -> dict:
    cliente = await _cliente(empresa_id, payload.cliente_id, s, obligatorio=False)
    caja = await _caja_pos(empresa_id, payload.caja_id, s)
    items, subtotal, iva_total, inc_total = await _totalizar(empresa_id, payload.items, s)
    return {
        **payload.model_dump(exclude={"items"}),
        "cliente_nombre": (cliente or {}).get("nombre", "Consumidor final"),
        "caja_id": str(caja["_id"]),
        "caja_nombre": caja.get("nombre", ""),
        "items": items,
        "subtotal": subtotal,
        "iva_total": iva_total,
        "inc_total": inc_total,
        "total": redondear(subtotal + iva_total + inc_total, 2),
        "estado": "emitido",
        "estado_dian": "borrador",
    }


@router.get("/documento-equivalente-pos")
async def listar_pos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    cursor = get_db().documentos_pos.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/documento-equivalente-pos", status_code=201)
async def crear_pos(
    payload: PosCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_pos(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "pos", s)
        doc.update({
            "empresa_id": empresa_id, "prefijo": "POS", "consecutivo": consecutivo,
            "numero": formatear_numero("POS", consecutivo), "creado_por": usuario["id"],
            "fecha_creacion": ahora(),
        })
        res = await db.documentos_pos.insert_one(doc, session=s)
        did = str(res.inserted_id)
        await _efectos_pos(empresa_id, did, doc, usuario["id"], s)
        await auditar(empresa_id, POS, did, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.documentos_pos.find_one({"_id": nuevo}))


@router.put("/documento-equivalente-pos/{did}")
async def editar_pos(
    did: str,
    payload: PosCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("documentos_pos", empresa_id, did, s)
        if existente.get("estado_dian", "borrador") != "borrador":
            raise HTTPException(409, "El documento ya fue enviado a la DIAN")
        await _revertir_pos(empresa_id, did, s, recalcular=False)
        doc = await _armar_pos(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.documentos_pos.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _efectos_pos(empresa_id, did, doc, usuario["id"], s)
        await _recalcular_items_previos(empresa_id, existente, s)
        await auditar(empresa_id, POS, did, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.documentos_pos.find_one({"_id": oid(did)}))


@router.post("/documento-equivalente-pos/{did}/anular")
async def anular_pos(
    did: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("documentos_pos", empresa_id, did, s)
        if existente.get("estado_dian", "borrador") != "borrador":
            raise HTTPException(409, "El documento ya fue enviado a la DIAN")
        await _revertir_pos(empresa_id, did, s)
        await db.documentos_pos.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, POS, did, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.documentos_pos.find_one({"_id": oid(did)}))


# ---------------------------------------------------------------------------
# Notas crédito / débito (ajustan el saldo de la factura origen)
# ---------------------------------------------------------------------------

class ItemNota(BaseModel):
    descripcion: str = Field(min_length=1)
    cantidad: float = Field(default=1, gt=0)
    precio_unitario: float = Field(ge=0)
    tarifa_iva: float = Field(default=0, ge=0, le=100)


class NotaCrear(BaseModel):
    factura_id: str
    tipo: Literal["credito", "debito"]
    fecha: str
    motivo: str = Field(min_length=1)
    items: list[ItemNota] = Field(min_length=1)


NOTA = "nota"


async def _armar_nota(empresa_id: str, payload: NotaCrear, s) -> tuple[dict, dict]:
    db = get_db()
    factura = await db.facturas.find_one(
        {"_id": oid(payload.factura_id, "factura_id"), "empresa_id": empresa_id, **NO_ANULADO}, session=s
    )
    if not factura:
        raise HTTPException(404, "Factura origen no encontrada o anulada")
    subtotal = sum(i.cantidad * i.precio_unitario for i in payload.items)
    iva = sum(i.cantidad * i.precio_unitario * i.tarifa_iva / 100 for i in payload.items)
    items = [
        {**i.model_dump(), "subtotal": redondear(i.cantidad * i.precio_unitario, 2),
         "iva": redondear(i.cantidad * i.precio_unitario * i.tarifa_iva / 100, 2),
         "total": redondear(i.cantidad * i.precio_unitario * (1 + i.tarifa_iva / 100), 2)}
        for i in payload.items
    ]
    # Retenciones, autorretención e impuesto al consumo se trasladan en la misma proporción
    # que la nota representa respecto de la factura origen.
    base = float(factura.get("subtotal") or 0)
    proporcion = min(1.0, subtotal / base) if base else 0.0
    detalle, ret, total_ret = impuestos.prorratear_retenciones(factura.get("detalle_retenciones") or [], proporcion)
    inc_cuentas: dict[str, float] = defaultdict(float)
    for it in factura.get("items", []):
        if it.get("inc"):
            inc_cuentas[it["cuenta_inc"]] += it["inc"] * proporcion
    inc_cuentas = {c: redondear(v, 2) for c, v in inc_cuentas.items()}
    inc_total = redondear(sum(inc_cuentas.values()), 2)
    total = redondear(subtotal + iva + inc_total, 2)
    doc = {
        **payload.model_dump(exclude={"items"}),
        "factura_numero": factura.get("numero") or f"{factura.get('prefijo', '')}{factura.get('consecutivo', '')}",
        "cliente_id": factura.get("cliente_id"),
        "cliente_nombre": factura.get("cliente_nombre", ""),
        "items": items,
        "subtotal": redondear(subtotal, 2),
        "iva_total": redondear(iva, 2),
        "inc_total": inc_total,
        "inc_cuentas": inc_cuentas,
        "total": total,
        "retenciones": ret,
        "detalle_retenciones": detalle,
        "total_retenciones": total_ret,
        "autorretencion": redondear(float(factura.get("autorretencion") or 0) * proporcion, 2),
        "neto": redondear(total - total_ret, 2),
        "proporcion": redondear(proporcion, 6),
        "estado": "emitida",
        "estado_dian": "borrador",
    }
    return doc, factura


async def _aplicar_nota(empresa_id: str, nid: str, doc: dict, factura: dict, s) -> None:
    signo = -1 if doc["tipo"] == "credito" else 1
    nuevo_saldo = redondear(float(factura.get("saldo_pendiente", factura["total"])) + signo * doc["neto"], 2)
    if nuevo_saldo < -0.009:
        raise HTTPException(409, "La nota crédito supera el saldo pendiente de la factura")
    await get_db().facturas.update_one(
        {"_id": factura["_id"]}, {"$set": {"saldo_pendiente": nuevo_saldo}}, session=s
    )
    t = doc.get("cliente_id")
    params = await parametros.obtener(empresa_id, s)
    cxc = factura.get("cuenta_cxc") or params["clientes"]
    favor = impuestos.lineas_retencion(doc.get("detalle_retenciones") or [], params, "sufrida")
    inc = list((doc.get("inc_cuentas") or {}).items())
    autorret = doc.get("autorretencion") or 0
    if doc["tipo"] == "credito":  # reverso de la venta, con sus impuestos y retenciones
        lineas = [Linea(codigo=params["devoluciones"], debito=doc["subtotal"], tercero_id=t),
                  Linea(codigo=params["iva_generado"], debito=doc["iva_total"], tercero_id=t),
                  Linea(codigo=cxc, credito=doc["neto"], tercero_id=t)]
        lineas += [Linea(codigo=c, debito=v, tercero_id=t, descripcion="Impuesto al consumo") for c, v in inc]
        lineas += [Linea(codigo=c, credito=v, tercero_id=t, descripcion="Retención revertida") for c, v in favor]
        if autorret:
            lineas.append(Linea(codigo=params["autorretencion_pasivo"], debito=autorret, descripcion="Autorretención revertida"))
            lineas.append(Linea(codigo=params["autorretencion_anticipo"], credito=autorret, descripcion="Autorretención revertida"))
    else:
        lineas = [Linea(codigo=cxc, debito=doc["neto"], tercero_id=t),
                  Linea(codigo=params["ingresos"], credito=doc["subtotal"], tercero_id=t),
                  Linea(codigo=params["iva_generado"], credito=doc["iva_total"], tercero_id=t)]
        lineas += [Linea(codigo=c, credito=v, tercero_id=t, descripcion="Impuesto al consumo") for c, v in inc]
        lineas += [Linea(codigo=c, debito=v, tercero_id=t, descripcion="Retención practicada por el cliente") for c, v in favor]
        if autorret:
            lineas.append(Linea(codigo=params["autorretencion_anticipo"], debito=autorret, descripcion="Autorretención de renta"))
            lineas.append(Linea(codigo=params["autorretencion_pasivo"], credito=autorret, descripcion="Autorretención de renta"))
    await registrar_asientos(empresa_id, NOTA, nid, doc["numero"], doc["fecha"], lineas, s)


async def _revertir_nota(empresa_id: str, nota: dict, s) -> None:
    db = get_db()
    signo = -1 if nota["tipo"] == "credito" else 1
    await db.facturas.update_one(
        {"_id": oid(nota["factura_id"]), "empresa_id": empresa_id},
        {"$inc": {"saldo_pendiente": -signo * nota.get("neto", nota["total"])}},
        session=s,
    )
    await borrar_asientos(empresa_id, NOTA, str(nota["_id"]), s)


@router.get("/notas-credito-debito")
async def listar_notas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    cursor = get_db().notas_credito_debito.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/notas-credito-debito", status_code=201)
async def crear_nota(
    payload: NotaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc, factura = await _armar_nota(empresa_id, payload, s)
        prefijo = "NC" if payload.tipo == "credito" else "ND"
        consecutivo = await siguiente_consecutivo(empresa_id, f"nota:{payload.tipo}", s)
        doc.update({
            "empresa_id": empresa_id, "prefijo": prefijo, "consecutivo": consecutivo,
            "numero": formatear_numero(prefijo, consecutivo), "creado_por": usuario["id"],
            "fecha_creacion": ahora(),
        })
        res = await db.notas_credito_debito.insert_one(doc, session=s)
        nid = str(res.inserted_id)
        await _aplicar_nota(empresa_id, nid, doc, factura, s)
        await auditar(empresa_id, NOTA, nid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.notas_credito_debito.find_one({"_id": nuevo}))


@router.put("/notas-credito-debito/{nid}")
async def editar_nota(
    nid: str,
    payload: NotaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("notas_credito_debito", empresa_id, nid, s)
        if payload.tipo != existente["tipo"]:
            raise HTTPException(409, "No se puede cambiar el tipo de una nota ya numerada")
        await _revertir_nota(empresa_id, existente, s)
        doc, factura = await _armar_nota(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.notas_credito_debito.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar_nota(empresa_id, nid, doc, factura, s)
        await auditar(empresa_id, NOTA, nid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.notas_credito_debito.find_one({"_id": oid(nid)}))


@router.post("/notas-credito-debito/{nid}/anular")
async def anular_nota(
    nid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("notas_credito_debito", empresa_id, nid, s)
        await _revertir_nota(empresa_id, existente, s)
        await db.notas_credito_debito.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, NOTA, nid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.notas_credito_debito.find_one({"_id": oid(nid)}))
