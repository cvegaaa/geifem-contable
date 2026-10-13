"""Tesorería: cajas y bancos, movimientos, cartera (CxC/CxP) y pagos.

- Un movimiento manual de caja/banco exige cuenta de contrapartida para que
  el asiento cuadre.
- Un pago (recibo de caja RC o comprobante de egreso CE) se cruza contra una
  factura: baja su saldo, genera el movimiento de caja/banco y el asiento.
  Anularlo devuelve el saldo a la factura.
- El saldo de cada caja/banco se calcula con los movimientos no anulados.
"""
from collections import defaultdict
from datetime import date, datetime, timezone
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
tesoreria = APIRouter(prefix="/api/tesoreria", tags=["tesoreria"])

# Parámetro de respaldo cuando la caja o el banco no tiene cuenta contable propia.
PARAMETRO_POR_TIPO = {"caja": "caja", "banco": "bancos"}
COLECCION_POR_TIPO = {"caja": "cajas", "banco": "cuentas_bancarias"}

# Alias usados por la conciliación bancaria (más abajo).
_serialize = serializar
_oid = oid


class Anulacion(BaseModel):
    motivo: str | None = None


async def _validar_cuenta(db, empresa_id: str, cuenta_tipo: str, cuenta_id: str, s=None) -> dict:
    if cuenta_tipo not in COLECCION_POR_TIPO:
        raise HTTPException(422, "cuenta_tipo debe ser 'caja' o 'banco'")
    doc = await db[COLECCION_POR_TIPO[cuenta_tipo]].find_one(
        {"_id": oid(cuenta_id, "cuenta_id"), "empresa_id": empresa_id}, session=s
    )
    if not doc:
        raise HTTPException(404, "Cuenta de tesorería no encontrada")
    return doc


async def cuenta_contable_de(empresa_id: str, cuenta_tipo: str, cuenta: dict, s=None) -> str:
    """Cuenta PUC de una caja/banco: la propia o la de los parámetros de la empresa."""
    if cuenta.get("cuenta_contable"):
        return cuenta["cuenta_contable"]
    return (await parametros.obtener(empresa_id, s))[PARAMETRO_POR_TIPO[cuenta_tipo]]


def _lineas_tesoreria(mov: dict, codigo_contrapartida: str) -> list[Linea]:
    valor = mov["valor"]
    ingreso = mov["tipo"] == "ingreso"
    efectivo = mov["cuenta_contable"]
    t = mov.get("tercero_id")
    return [
        Linea(codigo=efectivo, debito=valor if ingreso else 0, credito=0 if ingreso else valor,
              tercero_id=t, descripcion=mov.get("concepto")),
        Linea(codigo=codigo_contrapartida, debito=0 if ingreso else valor, credito=valor if ingreso else 0,
              tercero_id=t, descripcion=mov.get("concepto")),
    ]


# ---------------------------------------------------------------------------
# Movimientos manuales de caja / banco
# ---------------------------------------------------------------------------

class MovimientoTesoreria(BaseModel):
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    tipo: Literal["ingreso", "egreso"]
    fecha: str
    valor: float = Field(gt=0)
    concepto: str = Field(min_length=1)
    tercero_id: str | None = None
    cuenta_contrapartida: str = Field(min_length=4, description="Código PUC, p. ej. 4135 o 5195")


MOV = "movimiento_tesoreria"


async def _armar_movimiento(empresa_id: str, payload: MovimientoTesoreria, s) -> dict:
    cuenta = await _validar_cuenta(get_db(), empresa_id, payload.cuenta_tipo, payload.cuenta_id, s)
    return {**payload.model_dump(), "cuenta_nombre": cuenta.get("nombre", ""),
            "cuenta_contable": await cuenta_contable_de(empresa_id, payload.cuenta_tipo, cuenta, s),
            "origen": "manual",
            "estado": "registrado"}


@tesoreria.get("/movimientos")
async def listar_movimientos(
    cuenta_tipo: str | None = Query(None),
    cuenta_id: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if cuenta_tipo:
        filtro["cuenta_tipo"] = cuenta_tipo
    if cuenta_id:
        filtro["cuenta_id"] = cuenta_id
    if desde and hasta:
        filtro["fecha"] = {"$gte": desde, "$lte": hasta}
    cursor = get_db().movimientos_tesoreria.find(filtro).sort([("fecha", -1), ("fecha_creacion", -1)])
    return [serializar(d) async for d in cursor]


@tesoreria.post("/movimientos", status_code=201)
async def crear_movimiento(
    payload: MovimientoTesoreria,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _armar_movimiento(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "movimiento_tesoreria", s)
        doc.update({"empresa_id": empresa_id, "prefijo": "MT", "consecutivo": consecutivo,
                    "numero": formatear_numero("MT", consecutivo), "referencia": formatear_numero("MT", consecutivo),
                    "creado_por": usuario["id"], "fecha_creacion": ahora()})
        res = await db.movimientos_tesoreria.insert_one(doc, session=s)
        mid = str(res.inserted_id)
        await registrar_asientos(empresa_id, MOV, mid, doc["numero"], doc["fecha"],
                                 _lineas_tesoreria(doc, payload.cuenta_contrapartida), s)
        await auditar(empresa_id, MOV, mid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.movimientos_tesoreria.find_one({"_id": nuevo}))


async def _movimiento_modificable(empresa_id: str, mid: str, s) -> dict:
    mov = await cargar_editable("movimientos_tesoreria", empresa_id, mid, s)
    if mov.get("origen") != "manual":
        raise HTTPException(409, "Este movimiento proviene de otro documento (pago, venta POS o saldo inicial): modifícalo desde allí")
    if mov.get("conciliado"):
        raise HTTPException(409, "El movimiento ya está conciliado con el extracto bancario")
    return mov


@tesoreria.put("/movimientos/{mid}")
async def editar_movimiento(
    mid: str,
    payload: MovimientoTesoreria,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await _movimiento_modificable(empresa_id, mid, s)
        await borrar_asientos(empresa_id, MOV, mid, s)
        doc = await _armar_movimiento(empresa_id, payload, s)
        doc.update({**campos_conservados(existente), "referencia": existente.get("numero"),
                    "editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.movimientos_tesoreria.replace_one({"_id": existente["_id"]}, doc, session=s)
        await registrar_asientos(empresa_id, MOV, mid, doc["numero"], doc["fecha"],
                                 _lineas_tesoreria(doc, payload.cuenta_contrapartida), s)
        await auditar(empresa_id, MOV, mid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.movimientos_tesoreria.find_one({"_id": oid(mid)}))


@tesoreria.post("/movimientos/{mid}/anular")
async def anular_movimiento(
    mid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await _movimiento_modificable(empresa_id, mid, s)
        await borrar_asientos(empresa_id, MOV, mid, s)
        await db.movimientos_tesoreria.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, MOV, mid, existente.get("numero"), usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.movimientos_tesoreria.find_one({"_id": oid(mid)}))


async def _saldo_cuenta(db, empresa_id: str, cuenta_tipo: str, cuenta_id: str, base: float) -> float:
    saldo = base
    async for m in db.movimientos_tesoreria.find(
        {"empresa_id": empresa_id, "cuenta_tipo": cuenta_tipo, "cuenta_id": cuenta_id, **NO_ANULADO}
    ):
        saldo += m["valor"] if m["tipo"] == "ingreso" else -m["valor"]
    return redondear(saldo, 2)


async def _listar_cuentas(empresa_id: str, cuenta_tipo: str) -> list[dict]:
    db = get_db()
    salida = []
    async for c in db[COLECCION_POR_TIPO[cuenta_tipo]].find(
        {"empresa_id": empresa_id, "activo": {"$ne": False}}
    ):
        doc = serializar(c)
        # El saldo inicial contabilizado ya es un movimiento; solo las cuentas
        # anteriores a esta regla lo suman aparte.
        base = 0.0 if doc.get("saldo_inicial_contabilizado") else float(doc.get("saldo_inicial", 0) or 0)
        doc["saldo"] = await _saldo_cuenta(db, empresa_id, cuenta_tipo, doc["id"], base)
        salida.append(doc)
    return salida


@tesoreria.get("/caja")
async def listar_caja(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    return await _listar_cuentas(empresa_id, "caja")


@tesoreria.get("/bancos")
async def listar_bancos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    return await _listar_cuentas(empresa_id, "banco")


# ---------------------------------------------------------------------------
# Cartera CxC / CxP
# ---------------------------------------------------------------------------

async def _cartera(empresa_id: str) -> dict:
    db = get_db()
    cxc, cxp = [], []
    async for f in db.facturas.find({"empresa_id": empresa_id, **NO_ANULADO}).sort("fecha", 1):
        total = float(f.get("total", 0))
        saldo = float(f.get("saldo_pendiente", total))
        if saldo <= 0.009:
            continue
        cxc.append({
            "id": str(f["_id"]), "tipo": "cxc",
            "documento": f.get("numero") or f"{f.get('prefijo', '')}{f.get('consecutivo', '')}",
            "tercero": f.get("cliente_nombre", ""), "tercero_id": f.get("cliente_id"),
            "fecha": f.get("fecha"), "vencimiento": f.get("fecha_vencimiento"),
            "total": redondear(total, 2), "saldo": redondear(saldo, 2),
        })
    async for f in db.facturas_proveedor.find({"empresa_id": empresa_id, **NO_ANULADO}).sort("fecha", 1):
        total = float(f.get("total_a_pagar", f.get("total", 0)))
        saldo = float(f.get("saldo_pendiente", total))
        if saldo <= 0.009:
            continue
        cxp.append({
            "id": str(f["_id"]), "tipo": "cxp",
            "documento": f.get("numero_factura", ""),
            "tercero": f.get("proveedor_nombre", ""), "tercero_id": f.get("proveedor_id"),
            "fecha": f.get("fecha"), "vencimiento": f.get("fecha_vencimiento"),
            "total": redondear(total, 2), "saldo": redondear(saldo, 2),
        })
    return {
        "cxc": cxc, "cxp": cxp,
        "resumen": {
            "total_cxc": redondear(sum(d["saldo"] for d in cxc), 2),
            "total_cxp": redondear(sum(d["saldo"] for d in cxp), 2),
        },
    }


@tesoreria.get("/cxc-cxp")
async def cxc_cxp(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    return await _cartera(empresa_id)


TRAMOS = (("no_vencido", "No vencido"), ("d1_30", "1-30 días"), ("d31_60", "31-60 días"),
          ("d61_90", "61-90 días"), ("d90_mas", "Más de 90 días"))


def _tramo(dias_mora: int) -> str:
    if dias_mora <= 0:
        return "no_vencido"
    if dias_mora <= 30:
        return "d1_30"
    if dias_mora <= 60:
        return "d31_60"
    if dias_mora <= 90:
        return "d61_90"
    return "d90_mas"


def _fecha(valor: str | None, defecto: date) -> date:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return defecto


@tesoreria.get("/cartera/antiguedad")
async def antiguedad_cartera(
    tipo: Literal["cxc", "cxp"] = "cxc",
    corte: str | None = Query(None, description="Fecha de corte (AAAA-MM-DD); por defecto hoy"),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    """Cartera por edades: saldo pendiente por tercero según los días de mora al corte."""
    hoy = _fecha(corte, date.today())
    docs = (await _cartera(empresa_id))[tipo]
    por_tercero: dict[str, dict] = {}
    for d in docs:
        mora = (hoy - _fecha(d.get("vencimiento") or d.get("fecha"), hoy)).days
        clave = d.get("tercero_id") or d.get("tercero") or "—"
        fila = por_tercero.setdefault(clave, {
            "tercero_id": d.get("tercero_id"), "tercero": d.get("tercero") or "Sin tercero",
            "documentos": 0, "total": 0.0, **{k: 0.0 for k, _ in TRAMOS},
        })
        fila[_tramo(mora)] += d["saldo"]
        fila["total"] += d["saldo"]
        fila["documentos"] += 1
    filas = sorted(por_tercero.values(), key=lambda f: -f["total"])
    for f in filas:
        for k in ["total"] + [k for k, _ in TRAMOS]:
            f[k] = redondear(f[k], 2)
    totales = {k: redondear(sum(f[k] for f in filas), 2) for k in ["total"] + [k for k, _ in TRAMOS]}
    return {"tipo": tipo, "corte": hoy.isoformat(), "tramos": [{"clave": k, "etiqueta": e} for k, e in TRAMOS],
            "filas": filas, "totales": totales}


@tesoreria.get("/cartera/estado-cuenta")
async def estado_cuenta(
    tercero_id: str,
    tipo: Literal["cxc", "cxp"] = "cxc",
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    """Estado de cuenta de un tercero: facturas con su saldo y los pagos aplicados."""
    db = get_db()
    es_cxc = tipo == "cxc"
    coleccion = "facturas" if es_cxc else "facturas_proveedor"
    campo_tercero = "cliente_id" if es_cxc else "proveedor_id"
    facturas, total, saldo = [], 0.0, 0.0
    async for f in db[coleccion].find({"empresa_id": empresa_id, campo_tercero: tercero_id, **NO_ANULADO}).sort("fecha", 1):
        t = float(f.get("total", 0) if es_cxc else f.get("total_a_pagar", f.get("total", 0)))
        sd = float(f.get("saldo_pendiente", t))
        facturas.append({
            "id": str(f["_id"]),
            "documento": (f.get("numero") if es_cxc else f.get("numero_factura")) or "",
            "fecha": f.get("fecha"), "vencimiento": f.get("fecha_vencimiento"),
            "total": redondear(t, 2), "saldo": redondear(sd, 2),
            "estado": "pagada" if sd <= 0.009 else ("parcial" if sd < t - 0.009 else "pendiente"),
        })
        total += t
        saldo += sd
    pagos = []
    async for p in db.pagos.find({"empresa_id": empresa_id, "tercero_id": tercero_id,
                                  "documento_tipo": tipo, **NO_ANULADO}).sort("fecha", 1):
        pagos.append({"id": str(p["_id"]), "numero": p.get("numero"), "fecha": p.get("fecha"),
                      "documento": p.get("documento_numero"), "valor": redondear(float(p.get("valor", 0)), 2)})
    tercero = await db.terceros.find_one({"_id": oid(tercero_id, "tercero_id"), "empresa_id": empresa_id})
    anticipos = [
        {"id": str(a["_id"]), "numero": a.get("numero"), "fecha": a.get("fecha"), "valor": a.get("valor"), "saldo": a.get("saldo")}
        async for a in db.anticipos.find({"empresa_id": empresa_id, "tercero_id": tercero_id,
                                           "tipo": "cliente" if es_cxc else "proveedor", "saldo": {"$gt": 0.009}, **NO_ANULADO})
    ]
    return {
        "anticipos_disponibles": anticipos,
        "tipo": tipo, "tercero": (tercero or {}).get("nombre", ""), "documento": (tercero or {}).get("numero_documento", ""),
        "facturas": facturas, "pagos": pagos,
        "resumen": {"facturado": redondear(total, 2), "pagado": redondear(total - saldo, 2), "saldo": redondear(saldo, 2)},
    }


# ---------------------------------------------------------------------------
# Pagos: recibo de caja (cxc) / comprobante de egreso (cxp)
# ---------------------------------------------------------------------------

class PagoCrear(BaseModel):
    documento_tipo: Literal["cxc", "cxp"]
    documento_id: str
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    fecha: str
    valor: float = Field(gt=0)
    observaciones: str | None = None


PAGO = "pago"


async def _aplicar_pago(empresa_id: str, pid: str, pago: dict, usuario_id: str, s) -> dict:
    """Baja el saldo de la factura, crea el movimiento de caja/banco y el asiento."""
    db = get_db()
    cuenta = await _validar_cuenta(db, empresa_id, pago["cuenta_tipo"], pago["cuenta_id"], s)
    coleccion = "facturas" if pago["documento_tipo"] == "cxc" else "facturas_proveedor"
    factura = await db[coleccion].find_one(
        {"_id": oid(pago["documento_id"], "documento_id"), "empresa_id": empresa_id, **NO_ANULADO}, session=s
    )
    if not factura:
        raise HTTPException(404, "Factura no encontrada o anulada")
    total = float(factura.get("total_a_pagar", factura.get("total", 0)) if pago["documento_tipo"] == "cxp"
                  else factura.get("total", 0))
    saldo = float(factura.get("saldo_pendiente", total))
    if pago["valor"] > saldo + 0.009:
        raise HTTPException(409, f"El valor supera el saldo pendiente ({saldo:,.2f})")
    nuevo_saldo = redondear(saldo - pago["valor"], 2)
    await db[coleccion].update_one(
        {"_id": factura["_id"]},
        {"$set": {"saldo_pendiente": nuevo_saldo,
                  "estado_pago": "pagada" if nuevo_saldo <= 0.009 else "parcial"}},
        session=s,
    )
    es_cxc = pago["documento_tipo"] == "cxc"
    tercero_id = factura.get("cliente_id") if es_cxc else factura.get("proveedor_id")
    documento_numero = factura.get("numero") if es_cxc else factura.get("numero_factura", "")
    info = {
        "tercero_id": tercero_id,
        "tercero_nombre": factura.get("cliente_nombre") if es_cxc else factura.get("proveedor_nombre", ""),
        "documento_numero": documento_numero,
        "cuenta_nombre": cuenta.get("nombre", ""),
        "saldo_resultante": nuevo_saldo,
    }
    mov = {
        "empresa_id": empresa_id,
        "cuenta_tipo": pago["cuenta_tipo"], "cuenta_id": pago["cuenta_id"], "cuenta_nombre": cuenta.get("nombre", ""),
        "cuenta_contable": await cuenta_contable_de(empresa_id, pago["cuenta_tipo"], cuenta, s),
        "tipo": "ingreso" if es_cxc else "egreso",
        "fecha": pago["fecha"], "valor": pago["valor"],
        "concepto": f"{'Recaudo' if es_cxc else 'Pago'} {documento_numero}",
        "tercero_id": tercero_id,
        "numero": pago["numero"], "referencia": pago["numero"],
        "origen": "cruce_cartera", "estado": "registrado",
        "documento_tipo": PAGO, "documento_id": pid,
        "creado_por": usuario_id, "fecha_creacion": ahora(),
    }
    await db.movimientos_tesoreria.insert_one(mov, session=s)
    await registrar_asientos(empresa_id, PAGO, pid, pago["numero"], pago["fecha"],
                             _lineas_tesoreria(mov, await _cuenta_cartera(empresa_id, factura, es_cxc, s)), s)
    return info


async def _cuenta_cartera(empresa_id: str, factura: dict, es_cxc: bool, s) -> str:
    """El pago cruza contra la misma cuenta con que se contabilizó la factura."""
    guardada = factura.get("cuenta_cxc" if es_cxc else "cuenta_cxp")
    if guardada:
        return guardada
    return (await parametros.obtener(empresa_id, s))["clientes" if es_cxc else "proveedores"]


async def _validar_cuenta_tesoreria(payload: dict, empresa_id: str) -> None:
    await parametros.validar_codigos(empresa_id, {"Cuenta contable": payload.get("cuenta_contable")})


async def _revertir_pago(empresa_id: str, pago: dict, s) -> None:
    db = get_db()
    pid = str(pago["_id"])
    coleccion = "facturas" if pago["documento_tipo"] == "cxc" else "facturas_proveedor"
    factura = await db[coleccion].find_one(
        {"_id": oid(pago["documento_id"]), "empresa_id": empresa_id}, session=s
    )
    if factura:
        saldo = redondear(float(factura.get("saldo_pendiente", 0)) + pago["valor"], 2)
        await db[coleccion].update_one(
            {"_id": factura["_id"]}, {"$set": {"saldo_pendiente": saldo, "estado_pago": "parcial"}}, session=s
        )
    mov = await db.movimientos_tesoreria.find_one(
        {"empresa_id": empresa_id, "documento_tipo": PAGO, "documento_id": pid}, session=s
    )
    if mov and mov.get("conciliado"):
        raise HTTPException(409, "El movimiento del pago ya está conciliado con el extracto bancario")
    await db.movimientos_tesoreria.delete_many(
        {"empresa_id": empresa_id, "documento_tipo": PAGO, "documento_id": pid}, session=s
    )
    await borrar_asientos(empresa_id, PAGO, pid, s)


@tesoreria.get("/pagos")
async def listar_pagos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    cursor = get_db().pagos.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("fecha_creacion", -1)])
    return [serializar(d) async for d in cursor]


async def _crear_pago(empresa_id: str, datos: dict, usuario_id: str, s, extra: dict | None = None):
    """Numera, guarda y aplica un recibo de caja (cxc) o comprobante de egreso (cxp)."""
    db = get_db()
    prefijo = "RC" if datos["documento_tipo"] == "cxc" else "CE"
    consecutivo = await siguiente_consecutivo(empresa_id, f"pago:{prefijo}", s)
    doc = {**datos, **(extra or {}), "empresa_id": empresa_id, "prefijo": prefijo,
           "consecutivo": consecutivo, "numero": formatear_numero(prefijo, consecutivo),
           "estado": "registrado", "creado_por": usuario_id, "fecha_creacion": ahora()}
    doc["referencia"] = doc["numero"]
    res = await db.pagos.insert_one(doc, session=s)
    pid = str(res.inserted_id)
    info = await _aplicar_pago(empresa_id, pid, doc, usuario_id, s)
    await db.pagos.update_one({"_id": res.inserted_id}, {"$set": info}, session=s)
    await auditar(empresa_id, PAGO, pid, doc["numero"], usuario_id, "creado", s)
    return res.inserted_id


@tesoreria.post("/pagos", status_code=201)
async def registrar_pago(
    payload: PagoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    nuevo = await en_transaccion(lambda s: _crear_pago(empresa_id, payload.model_dump(), usuario["id"], s))
    return serializar(await get_db().pagos.find_one({"_id": nuevo}))


class AplicacionPago(BaseModel):
    documento_id: str
    valor: float = Field(gt=0)


class PagoMultiple(BaseModel):
    documento_tipo: Literal["cxc", "cxp"]
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    fecha: str
    observaciones: str | None = None
    aplicaciones: list[AplicacionPago] = Field(min_length=1, max_length=100)


@tesoreria.post("/pagos/multiple", status_code=201)
async def registrar_pago_multiple(
    payload: PagoMultiple,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    """Un mismo pago o recaudo que cubre varias facturas: genera un recibo por factura, ligados por `lote`."""
    ids = [a.documento_id for a in payload.aplicaciones]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Una factura no puede repetirse en el mismo pago")

    async def _tx(s):
        lote = ahora().strftime("%Y%m%d%H%M%S%f")
        nuevos = []
        for a in payload.aplicaciones:
            datos = {"documento_tipo": payload.documento_tipo, "documento_id": a.documento_id,
                     "cuenta_tipo": payload.cuenta_tipo, "cuenta_id": payload.cuenta_id,
                     "fecha": payload.fecha, "valor": a.valor, "observaciones": payload.observaciones}
            nuevos.append(await _crear_pago(empresa_id, datos, usuario["id"], s, {"lote": lote}))
        return nuevos

    nuevos = await en_transaccion(_tx)
    return [serializar(d) async for d in get_db().pagos.find({"_id": {"$in": nuevos}}).sort("consecutivo", 1)]


@tesoreria.put("/pagos/{pid}")
async def editar_pago(
    pid: str,
    payload: PagoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "editar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("pagos", empresa_id, pid, s)
        if payload.documento_tipo != existente["documento_tipo"]:
            raise HTTPException(409, "No se puede cambiar un recibo de caja por un egreso (ni al revés)")
        await _revertir_pago(empresa_id, existente, s)
        doc = {**payload.model_dump(), **campos_conservados(existente), "estado": "registrado",
               "referencia": existente["numero"], "editado_por": usuario["id"], "fecha_actualizacion": ahora()}
        info = await _aplicar_pago(empresa_id, pid, doc, usuario["id"], s)
        await db.pagos.replace_one({"_id": existente["_id"]}, {**doc, **info}, session=s)
        await auditar(empresa_id, PAGO, pid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.pagos.find_one({"_id": oid(pid)}))


@tesoreria.post("/pagos/{pid}/anular")
async def anular_pago(
    pid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("pagos", empresa_id, pid, s)
        await _revertir_pago(empresa_id, existente, s)
        await db.pagos.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, PAGO, pid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.pagos.find_one({"_id": oid(pid)}))


# ---------------------------------------------------------------------------
# Flujo de caja
# ---------------------------------------------------------------------------

@tesoreria.get("/flujo-caja")
async def flujo_caja(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    db = get_db()
    por_dia: dict[str, dict[str, float]] = defaultdict(lambda: {"ingresos": 0.0, "egresos": 0.0})
    async for m in db.movimientos_tesoreria.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}, "origen": {"$ne": "transferencia"}, **NO_ANULADO}
    ):
        clave = "ingresos" if m["tipo"] == "ingreso" else "egresos"
        por_dia[m["fecha"]][clave] += float(m.get("valor", 0))

    filas, acumulado = [], 0.0
    for fecha in sorted(por_dia):
        ing = redondear(por_dia[fecha]["ingresos"], 2)
        egr = redondear(por_dia[fecha]["egresos"], 2)
        acumulado += ing - egr
        filas.append({"fecha": fecha, "ingresos": ing, "egresos": egr,
                      "neto": redondear(ing - egr, 2), "acumulado": redondear(acumulado, 2)})

    total_ing = redondear(sum(f["ingresos"] for f in filas), 2)
    total_egr = redondear(sum(f["egresos"] for f in filas), 2)
    return {
        "periodo": {"desde": desde, "hasta": hasta},
        "columnas": [
            {"key": "fecha", "label": "Fecha"},
            {"key": "ingresos", "label": "Ingresos"},
            {"key": "egresos", "label": "Egresos"},
            {"key": "neto", "label": "Neto"},
            {"key": "acumulado", "label": "Acumulado"},
        ],
        "filas": filas,
        "resumen": {"ingresos": total_ing, "egresos": total_egr,
                    "neto": redondear(total_ing - total_egr, 2)},
    }


# ---------------------------------------------------------------------------
# Conciliación bancaria automática — FASE 3
# ---------------------------------------------------------------------------

class LineaExtracto(BaseModel):
    fecha: str
    descripcion: str
    valor: float  # positivo = crédito (ingreso), negativo = débito (egreso)
    referencia: str | None = None


class ExtractoCargar(BaseModel):
    cuenta_id: str
    lineas: list[LineaExtracto]


class ConciliacionConfirmar(BaseModel):
    cuenta_id: str
    pares: list[dict]  # [{extracto_id, movimiento_id}]


@tesoreria.post("/conciliacion/extracto", status_code=201)
async def cargar_extracto(
    payload: ExtractoCargar,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    """Carga las líneas del extracto bancario para una cuenta."""
    await _validar_cuenta(db := get_db(), empresa_id, "banco", payload.cuenta_id)
    if not payload.lineas:
        raise HTTPException(422, "El extracto no tiene líneas")
    ahora = datetime.now(timezone.utc)
    docs = [
        {
            **l.model_dump(), "empresa_id": empresa_id, "cuenta_id": payload.cuenta_id,
            "conciliado": False, "movimiento_id": None,
            "creado_por": usuario["id"], "fecha_creacion": ahora,
        }
        for l in payload.lineas
    ]
    res = await db.extractos_bancarios.insert_many(docs)
    return {"cargadas": len(res.inserted_ids), "cuenta_id": payload.cuenta_id}


def _similar(desc: str, concepto: str) -> bool:
    a = {p for p in desc.lower().split() if len(p) > 3}
    b = {p for p in (concepto or "").lower().split() if len(p) > 3}
    return bool(a & b)


@tesoreria.get("/conciliacion-bancaria-auto")
async def conciliacion_auto(
    cuenta_id: str = Query(...),
    tolerancia_dias: int = Query(3, ge=0, le=15),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    """Cruza automáticamente el extracto contra los movimientos del libro.

    Regla: mismo valor absoluto y mismo signo, fecha dentro de la tolerancia.
    Si hay varios candidatos gana el de fecha más cercana; la coincidencia de
    palabras en la descripción sube la confianza a 'alta'.
    """
    db = get_db()
    await _validar_cuenta(db, empresa_id, "banco", cuenta_id)

    extracto = [
        _serialize(d)
        async for d in db.extractos_bancarios.find(
            {"empresa_id": empresa_id, "cuenta_id": cuenta_id, "conciliado": False}
        ).sort("fecha", 1)
    ]
    movimientos = [
        _serialize(d)
        async for d in db.movimientos_tesoreria.find(
            {"empresa_id": empresa_id, "cuenta_tipo": "banco", "cuenta_id": cuenta_id,
             "conciliado": {"$ne": True}, **NO_ANULADO}
        ).sort("fecha", 1)
    ]

    def dias(a: str, b: str) -> int:
        try:
            return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).days)
        except Exception:
            return 999

    usados: set[str] = set()
    conciliados, sin_par = [], []
    for lin in extracto:
        signo_ext = "ingreso" if lin["valor"] >= 0 else "egreso"
        valor_ext = redondear(abs(lin["valor"]), 2)
        candidatos = [
            m for m in movimientos
            if m["id"] not in usados
            and m["tipo"] == signo_ext
            and abs(redondear(float(m["valor"]), 2) - valor_ext) <= 0.01
            and dias(m["fecha"], lin["fecha"]) <= tolerancia_dias
        ]
        if not candidatos:
            sin_par.append(lin)
            continue
        mejor = min(candidatos, key=lambda m: dias(m["fecha"], lin["fecha"]))
        usados.add(mejor["id"])
        conciliados.append({
            "extracto_id": lin["id"], "movimiento_id": mejor["id"],
            "fecha_extracto": lin["fecha"], "fecha_libro": mejor["fecha"],
            "descripcion": lin["descripcion"], "concepto": mejor.get("concepto", ""),
            "referencia": mejor.get("referencia", ""),
            "valor": valor_ext, "tipo": signo_ext,
            "diferencia_dias": dias(mejor["fecha"], lin["fecha"]),
            "confianza": (
                "alta"
                if dias(mejor["fecha"], lin["fecha"]) == 0
                or _similar(lin["descripcion"], mejor.get("concepto", ""))
                else "media"
            ),
        })

    libro_sin_par = [m for m in movimientos if m["id"] not in usados]
    return {
        "cuenta_id": cuenta_id,
        "resumen": {
            "lineas_extracto": len(extracto),
            "movimientos_libro": len(movimientos),
            "conciliados": len(conciliados),
            "extracto_sin_conciliar": len(sin_par),
            "libro_sin_conciliar": len(libro_sin_par),
        },
        "conciliados": conciliados,
        "extracto_sin_conciliar": sin_par,
        "libro_sin_conciliar": libro_sin_par,
    }


@tesoreria.post("/conciliacion/confirmar")
async def confirmar_conciliacion(
    payload: ConciliacionConfirmar,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    """Marca como conciliados los pares aceptados por el usuario."""
    db = get_db()
    ahora = datetime.now(timezone.utc)
    aplicados = 0
    for par in payload.pares:
        ext_id = _oid(par.get("extracto_id", ""), "extracto_id")
        mov_id = _oid(par.get("movimiento_id", ""), "movimiento_id")
        r1 = await db.extractos_bancarios.update_one(
            {"_id": ext_id, "empresa_id": empresa_id},
            {"$set": {"conciliado": True, "movimiento_id": str(mov_id),
                      "conciliado_por": usuario["id"], "fecha_conciliacion": ahora}},
        )
        await db.movimientos_tesoreria.update_one(
            {"_id": mov_id, "empresa_id": empresa_id},
            {"$set": {"conciliado": True, "extracto_id": str(ext_id),
                      "conciliado_por": usuario["id"], "fecha_conciliacion": ahora}},
        )
        aplicados += 1 if r1.matched_count else 0
    return {"conciliados": aplicados}



# Anticipos y transferencias (documentos propios de tesorería).
from api.tesoreria import anticipos  # noqa: E402

tesoreria.include_router(anticipos.router)
router.include_router(tesoreria)


# ---------------------------------------------------------------------------
# Cajas y cuentas bancarias: cada una atada a su cuenta contable. El saldo inicial
# genera su propio asiento (contrapartida de los parámetros contables).
# ---------------------------------------------------------------------------

SALDO_INICIAL = "saldo_inicial"


class CuentaTesoreria(BaseModel):
    nombre: str = Field(min_length=1)
    banco: str | None = None
    numero_cuenta: str | None = None
    cuenta_contable: str | None = None
    saldo_inicial: float = Field(default=0, ge=0)


async def _contabilizar_saldo_inicial(empresa_id: str, tipo: str, cuenta: dict, usuario_id: str, s) -> None:
    valor = redondear(float(cuenta.get("saldo_inicial") or 0), 2)
    if valor <= 0:
        return
    cid = str(cuenta["_id"])
    params = await parametros.obtener(empresa_id, s)
    consecutivo = await siguiente_consecutivo(empresa_id, SALDO_INICIAL, s)
    numero = formatear_numero("SI", consecutivo)
    mov = {
        "empresa_id": empresa_id, "cuenta_tipo": tipo, "cuenta_id": cid, "cuenta_nombre": cuenta.get("nombre", ""),
        "cuenta_contable": cuenta["cuenta_contable"], "tipo": "ingreso", "fecha": cuenta.get("fecha_saldo") or hoy_iso(),
        "valor": valor, "concepto": "Saldo inicial", "numero": numero, "referencia": numero,
        "origen": SALDO_INICIAL, "estado": "registrado", "documento_tipo": SALDO_INICIAL, "documento_id": cid,
        "creado_por": usuario_id, "fecha_creacion": ahora(),
    }
    await get_db().movimientos_tesoreria.insert_one(mov, session=s)
    await registrar_asientos(empresa_id, SALDO_INICIAL, cid, numero, mov["fecha"],
                             _lineas_tesoreria(mov, params["saldos_iniciales"]), s)


async def _revertir_saldo_inicial(empresa_id: str, cid: str, s) -> None:
    await get_db().movimientos_tesoreria.delete_many(
        {"empresa_id": empresa_id, "documento_tipo": SALDO_INICIAL, "documento_id": cid}, session=s)
    await borrar_asientos(empresa_id, SALDO_INICIAL, cid, s)


def hoy_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _router_cuentas(tipo: str, prefijo: str) -> APIRouter:
    r = APIRouter(prefix=prefijo, tags=[f"tesoreria:{tipo}"])
    coleccion = COLECCION_POR_TIPO[tipo]

    async def _preparar(empresa_id: str, payload: CuentaTesoreria, s) -> dict:
        doc = payload.model_dump()
        doc["cuenta_contable"] = doc["cuenta_contable"] or await cuenta_contable_de(empresa_id, tipo, {}, s)
        await parametros.validar_codigos(empresa_id, {"Cuenta contable": doc["cuenta_contable"]})
        return doc

    @r.get("")
    async def listar(empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("tesoreria", "leer"))):
        return await _listar_cuentas(empresa_id, tipo)

    @r.post("", status_code=201)
    async def crear(
        payload: CuentaTesoreria,
        empresa_id: str = Depends(get_empresa_activa),
        usuario: dict = Depends(require_permiso("tesoreria", "crear")),
    ):
        db = get_db()

        async def _tx(s):
            doc = await _preparar(empresa_id, payload, s)
            doc.update({"empresa_id": empresa_id, "activo": True, "creado_por": usuario["id"],
                        "fecha_creacion": ahora(), "saldo_inicial_contabilizado": True})
            res = await db[coleccion].insert_one(doc, session=s)
            doc["_id"] = res.inserted_id
            await _contabilizar_saldo_inicial(empresa_id, tipo, doc, usuario["id"], s)
            await auditar(empresa_id, f"cuenta_{tipo}", str(res.inserted_id), doc["nombre"], usuario["id"], "creado", s)
            return res.inserted_id

        nuevo = await en_transaccion(_tx)
        return serializar(await db[coleccion].find_one({"_id": nuevo}))

    @r.put("/{cid}")
    async def editar(
        cid: str,
        payload: CuentaTesoreria,
        empresa_id: str = Depends(get_empresa_activa),
        usuario: dict = Depends(require_permiso("tesoreria", "editar")),
    ):
        db = get_db()

        async def _tx(s):
            existente = await db[coleccion].find_one({"_id": oid(cid), "empresa_id": empresa_id}, session=s)
            if not existente:
                raise HTTPException(404, "Cuenta no encontrada")
            doc = await _preparar(empresa_id, payload, s)
            otros = await db.movimientos_tesoreria.count_documents(
                {"empresa_id": empresa_id, "cuenta_id": cid, "documento_tipo": {"$ne": SALDO_INICIAL}, **NO_ANULADO},
                session=s)
            if otros and doc["cuenta_contable"] != existente.get("cuenta_contable"):
                raise HTTPException(
                    409, "La cuenta ya tiene movimientos contabilizados: no se puede cambiar su cuenta contable. "
                         "Crea una cuenta nueva y traslada el saldo con un movimiento.")
            await _revertir_saldo_inicial(empresa_id, cid, s)
            doc.update({"fecha_actualizacion": ahora(), "saldo_inicial_contabilizado": True})
            await db[coleccion].update_one({"_id": existente["_id"]}, {"$set": doc}, session=s)
            await _contabilizar_saldo_inicial(empresa_id, tipo, {**existente, **doc}, usuario["id"], s)
            await auditar(empresa_id, f"cuenta_{tipo}", cid, doc["nombre"], usuario["id"], "editado", s)

        await en_transaccion(_tx)
        return serializar(await db[coleccion].find_one({"_id": oid(cid)}))

    @r.post("/{cid}/inactivar")
    async def inactivar(
        cid: str,
        empresa_id: str = Depends(get_empresa_activa),
        _=Depends(require_permiso("tesoreria", "inactivar")),
    ):
        res = await get_db()[coleccion].update_one({"_id": oid(cid), "empresa_id": empresa_id}, {"$set": {"activo": False}})
        if not res.matched_count:
            raise HTTPException(404, "Cuenta no encontrada")
        return {"ok": True}

    return r


router.include_router(_router_cuentas("caja", "/api/tesoreria/cuentas-caja"))
router.include_router(_router_cuentas("banco", "/api/tesoreria/cuentas-bancarias"))

