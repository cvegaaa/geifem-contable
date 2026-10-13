"""Anticipos de clientes y a proveedores, su aplicación a facturas y transferencias entre cajas y bancos.

- Anticipo recibido (AC): entra dinero a caja/banco contra el pasivo «anticipos de clientes».
- Anticipo entregado (AD): sale dinero contra el activo «anticipos a proveedores».
- Aplicación (AA): cruza el anticipo contra una factura del mismo tercero (no mueve efectivo).
- Transferencia (TR): mueve dinero entre dos cajas/bancos propios.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import parametros
from core.auth.dependencies import get_empresa_activa, require_permiso
from core.documentos import (
    NO_ANULADO,
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
from core.dinero import redondear
from db import get_db

router = APIRouter()

ANTICIPO = "anticipo"
APLICACION = "aplicacion_anticipo"
TRANSFERENCIA = "transferencia"


def _tesoreria():
    # Import diferido: este módulo se carga desde api.tesoreria.
    import api.tesoreria as t
    return t


class Anulacion(BaseModel):
    motivo: str | None = None


# ---------------------------------------------------------------------------
# Anticipos
# ---------------------------------------------------------------------------

class AnticipoCrear(BaseModel):
    tipo: Literal["cliente", "proveedor"]
    tercero_id: str
    fecha: str
    valor: float = Field(gt=0)
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    observaciones: str | None = None


@router.get("/anticipos")
async def listar_anticipos(
    tipo: Literal["cliente", "proveedor"] | None = Query(None),
    tercero_id: str | None = Query(None),
    con_saldo: bool = Query(False),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if tipo:
        filtro["tipo"] = tipo
    if tercero_id:
        filtro["tercero_id"] = tercero_id
    if con_saldo:
        filtro.update(NO_ANULADO)
        filtro["saldo"] = {"$gt": 0.009}
    cursor = get_db().anticipos.find(filtro).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/anticipos", status_code=201)
async def crear_anticipo(
    payload: AnticipoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    db = get_db()
    t = _tesoreria()

    async def _tx(s):
        tercero = await db.terceros.find_one({"_id": oid(payload.tercero_id, "tercero_id"), "empresa_id": empresa_id}, session=s)
        if not tercero:
            raise HTTPException(404, "Tercero no encontrado")
        cuenta = await t._validar_cuenta(db, empresa_id, payload.cuenta_tipo, payload.cuenta_id, s)
        es_cli = payload.tipo == "cliente"
        prefijo = "AC" if es_cli else "AD"
        consecutivo = await siguiente_consecutivo(empresa_id, f"anticipo:{prefijo}", s)
        numero = formatear_numero(prefijo, consecutivo)
        valor = redondear(payload.valor, 2)
        doc = {**payload.model_dump(), "valor": valor, "saldo": valor, "empresa_id": empresa_id,
               "tercero_nombre": tercero.get("nombre", ""), "cuenta_nombre": cuenta.get("nombre", ""),
               "prefijo": prefijo, "consecutivo": consecutivo, "numero": numero, "estado": "registrado",
               "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.anticipos.insert_one(doc, session=s)
        aid = str(res.inserted_id)
        params = await parametros.obtener(empresa_id, s)
        mov = {
            "empresa_id": empresa_id, "cuenta_tipo": payload.cuenta_tipo, "cuenta_id": payload.cuenta_id,
            "cuenta_nombre": cuenta.get("nombre", ""),
            "cuenta_contable": await t.cuenta_contable_de(empresa_id, payload.cuenta_tipo, cuenta, s),
            "tipo": "ingreso" if es_cli else "egreso", "fecha": payload.fecha, "valor": valor,
            "concepto": f"Anticipo {'de' if es_cli else 'a'} {tercero.get('nombre', '')}",
            "tercero_id": payload.tercero_id, "numero": numero, "referencia": numero,
            "origen": "anticipo", "estado": "registrado", "documento_tipo": ANTICIPO, "documento_id": aid,
            "creado_por": usuario["id"], "fecha_creacion": ahora(),
        }
        await db.movimientos_tesoreria.insert_one(mov, session=s)
        contrapartida = params["anticipos_clientes" if es_cli else "anticipos_proveedores"]
        await registrar_asientos(empresa_id, ANTICIPO, aid, numero, payload.fecha,
                                 t._lineas_tesoreria(mov, contrapartida), s)
        await auditar(empresa_id, ANTICIPO, aid, numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.anticipos.find_one({"_id": nuevo}))


@router.post("/anticipos/{aid}/anular")
async def anular_anticipo(
    aid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        ant = await cargar_editable("anticipos", empresa_id, aid, s)
        if redondear(ant["saldo"], 2) != redondear(ant["valor"], 2):
            raise HTTPException(409, "El anticipo tiene aplicaciones: anúlalas primero")
        mov = await db.movimientos_tesoreria.find_one(
            {"empresa_id": empresa_id, "documento_tipo": ANTICIPO, "documento_id": aid}, session=s)
        if mov and mov.get("conciliado"):
            raise HTTPException(409, "El movimiento del anticipo ya está conciliado con el extracto bancario")
        await db.movimientos_tesoreria.delete_many(
            {"empresa_id": empresa_id, "documento_tipo": ANTICIPO, "documento_id": aid}, session=s)
        await borrar_asientos(empresa_id, ANTICIPO, aid, s)
        await db.anticipos.update_one(
            {"_id": ant["_id"]}, {"$set": {**marca_anulacion(usuario["id"], payload.motivo), "saldo": 0}}, session=s)
        await auditar(empresa_id, ANTICIPO, aid, ant["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.anticipos.find_one({"_id": oid(aid)}))


# ---------------------------------------------------------------------------
# Aplicación de anticipos a facturas
# ---------------------------------------------------------------------------

class AplicarAnticipo(BaseModel):
    documento_id: str
    fecha: str
    valor: float = Field(gt=0)


@router.get("/aplicaciones-anticipo")
async def listar_aplicaciones(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    cursor = get_db().aplicaciones_anticipo.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/anticipos/{aid}/aplicar", status_code=201)
async def aplicar_anticipo(
    aid: str,
    payload: AplicarAnticipo,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    db = get_db()
    t = _tesoreria()

    async def _tx(s):
        ant = await cargar_editable("anticipos", empresa_id, aid, s)
        es_cli = ant["tipo"] == "cliente"
        coleccion = "facturas" if es_cli else "facturas_proveedor"
        factura = await db[coleccion].find_one(
            {"_id": oid(payload.documento_id, "documento_id"), "empresa_id": empresa_id, **NO_ANULADO}, session=s)
        if not factura:
            raise HTTPException(404, "Factura no encontrada o anulada")
        if (factura.get("cliente_id") if es_cli else factura.get("proveedor_id")) != ant["tercero_id"]:
            raise HTTPException(409, "La factura es de otro tercero distinto al del anticipo")
        valor = redondear(payload.valor, 2)
        if valor > ant["saldo"] + 0.009:
            raise HTTPException(409, f"El valor supera el saldo del anticipo ({ant['saldo']:,.2f})")
        total = float(factura.get("total", 0) if es_cli else factura.get("total_a_pagar", factura.get("total", 0)))
        saldo = float(factura.get("saldo_pendiente", total))
        if valor > saldo + 0.009:
            raise HTTPException(409, f"El valor supera el saldo pendiente de la factura ({saldo:,.2f})")
        nuevo_saldo = redondear(saldo - valor, 2)
        await db[coleccion].update_one(
            {"_id": factura["_id"]},
            {"$set": {"saldo_pendiente": nuevo_saldo, "estado_pago": "pagada" if nuevo_saldo <= 0.009 else "parcial"}},
            session=s)
        await db.anticipos.update_one({"_id": ant["_id"]}, {"$set": {"saldo": redondear(ant["saldo"] - valor, 2)}}, session=s)
        consecutivo = await siguiente_consecutivo(empresa_id, "anticipo:AA", s)
        numero = formatear_numero("AA", consecutivo)
        documento_numero = (factura.get("numero") if es_cli else factura.get("numero_factura")) or ""
        doc = {"empresa_id": empresa_id, "prefijo": "AA", "consecutivo": consecutivo, "numero": numero,
               "anticipo_id": aid, "anticipo_numero": ant["numero"], "tipo": ant["tipo"],
               "tercero_id": ant["tercero_id"], "tercero_nombre": ant.get("tercero_nombre", ""),
               "documento_id": payload.documento_id, "documento_numero": documento_numero,
               "fecha": payload.fecha, "valor": valor, "saldo_resultante": nuevo_saldo, "estado": "registrado",
               "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.aplicaciones_anticipo.insert_one(doc, session=s)
        params = await parametros.obtener(empresa_id, s)
        cartera = await t._cuenta_cartera(empresa_id, factura, es_cli, s)
        tercero = ant["tercero_id"]
        detalle = f"Aplicación {ant['numero']}"
        if es_cli:
            lineas = [Linea(codigo=params["anticipos_clientes"], debito=valor, tercero_id=tercero, descripcion=detalle),
                      Linea(codigo=cartera, credito=valor, tercero_id=tercero, descripcion=detalle)]
        else:
            lineas = [Linea(codigo=cartera, debito=valor, tercero_id=tercero, descripcion=detalle),
                      Linea(codigo=params["anticipos_proveedores"], credito=valor, tercero_id=tercero, descripcion=detalle)]
        await registrar_asientos(empresa_id, APLICACION, str(res.inserted_id), numero, payload.fecha, lineas, s)
        await auditar(empresa_id, APLICACION, str(res.inserted_id), numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.aplicaciones_anticipo.find_one({"_id": nuevo}))


@router.post("/aplicaciones-anticipo/{apid}/anular")
async def anular_aplicacion(
    apid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        ap = await cargar_editable("aplicaciones_anticipo", empresa_id, apid, s)
        coleccion = "facturas" if ap["tipo"] == "cliente" else "facturas_proveedor"
        factura = await db[coleccion].find_one({"_id": oid(ap["documento_id"]), "empresa_id": empresa_id}, session=s)
        if factura:
            await db[coleccion].update_one(
                {"_id": factura["_id"]},
                {"$set": {"saldo_pendiente": redondear(float(factura.get("saldo_pendiente", 0)) + ap["valor"], 2),
                          "estado_pago": "parcial"}}, session=s)
        await db.anticipos.update_one({"_id": oid(ap["anticipo_id"])}, {"$inc": {"saldo": ap["valor"]}}, session=s)
        await borrar_asientos(empresa_id, APLICACION, apid, s)
        await db.aplicaciones_anticipo.update_one(
            {"_id": ap["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, APLICACION, apid, ap["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.aplicaciones_anticipo.find_one({"_id": oid(apid)}))


# ---------------------------------------------------------------------------
# Transferencias entre cajas y bancos
# ---------------------------------------------------------------------------

class TransferenciaCrear(BaseModel):
    origen_tipo: Literal["caja", "banco"]
    origen_id: str
    destino_tipo: Literal["caja", "banco"]
    destino_id: str
    fecha: str
    valor: float = Field(gt=0)
    concepto: str | None = None


@router.get("/transferencias")
async def listar_transferencias(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    cursor = get_db().transferencias.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/transferencias", status_code=201)
async def crear_transferencia(
    payload: TransferenciaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    if (payload.origen_tipo, payload.origen_id) == (payload.destino_tipo, payload.destino_id):
        raise HTTPException(422, "El origen y el destino deben ser distintos")
    db = get_db()
    t = _tesoreria()

    async def _tx(s):
        origen = await t._validar_cuenta(db, empresa_id, payload.origen_tipo, payload.origen_id, s)
        destino = await t._validar_cuenta(db, empresa_id, payload.destino_tipo, payload.destino_id, s)
        contable_o = await t.cuenta_contable_de(empresa_id, payload.origen_tipo, origen, s)
        contable_d = await t.cuenta_contable_de(empresa_id, payload.destino_tipo, destino, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "transferencia", s)
        numero = formatear_numero("TR", consecutivo)
        valor = redondear(payload.valor, 2)
        concepto = payload.concepto or f"Traslado de {origen.get('nombre', '')} a {destino.get('nombre', '')}"
        doc = {**payload.model_dump(), "valor": valor, "concepto": concepto, "empresa_id": empresa_id,
               "origen_nombre": origen.get("nombre", ""), "destino_nombre": destino.get("nombre", ""),
               "prefijo": "TR", "consecutivo": consecutivo, "numero": numero, "estado": "registrado",
               "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.transferencias.insert_one(doc, session=s)
        tid = str(res.inserted_id)
        base = {"empresa_id": empresa_id, "fecha": payload.fecha, "valor": valor, "concepto": concepto,
                "numero": numero, "referencia": numero, "origen": "transferencia", "estado": "registrado",
                "documento_tipo": TRANSFERENCIA, "documento_id": tid, "creado_por": usuario["id"],
                "fecha_creacion": ahora()}
        await db.movimientos_tesoreria.insert_many([
            {**base, "cuenta_tipo": payload.origen_tipo, "cuenta_id": payload.origen_id,
             "cuenta_nombre": origen.get("nombre", ""), "cuenta_contable": contable_o, "tipo": "egreso"},
            {**base, "cuenta_tipo": payload.destino_tipo, "cuenta_id": payload.destino_id,
             "cuenta_nombre": destino.get("nombre", ""), "cuenta_contable": contable_d, "tipo": "ingreso"},
        ], session=s)
        await registrar_asientos(empresa_id, TRANSFERENCIA, tid, numero, payload.fecha, [
            Linea(codigo=contable_d, debito=valor, descripcion=concepto),
            Linea(codigo=contable_o, credito=valor, descripcion=concepto)], s)
        await auditar(empresa_id, TRANSFERENCIA, tid, numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.transferencias.find_one({"_id": nuevo}))


@router.post("/transferencias/{tid}/anular")
async def anular_transferencia(
    tid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        tr = await cargar_editable("transferencias", empresa_id, tid, s)
        filtro = {"empresa_id": empresa_id, "documento_tipo": TRANSFERENCIA, "documento_id": tid}
        if await db.movimientos_tesoreria.find_one({**filtro, "conciliado": True}, session=s):
            raise HTTPException(409, "Un movimiento de la transferencia ya está conciliado con el extracto bancario")
        await db.movimientos_tesoreria.delete_many(filtro, session=s)
        await borrar_asientos(empresa_id, TRANSFERENCIA, tid, s)
        await db.transferencias.update_one(
            {"_id": tr["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, TRANSFERENCIA, tid, tr["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.transferencias.find_one({"_id": oid(tid)}))
