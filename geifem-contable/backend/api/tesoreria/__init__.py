"""Tesorería — FASE 2.

Cajas y cuentas bancarias (CRUD), movimientos de tesorería con asiento
contable espejo, cartera CxC/CxP con cruce de pagos contra documentos y
flujo de caja por día. La conciliación bancaria automática sigue en Fase 3.
"""
from collections import defaultdict
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api._crud import crud_router
from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter()

tesoreria = APIRouter(prefix="/api/tesoreria", tags=["tesoreria"])

_F3 = "Módulo pendiente — Fase 3"

CUENTA_PUC_POR_TIPO = {"caja": "1105", "banco": "1110"}
COLECCION_POR_TIPO = {"caja": "cajas", "banco": "cuentas_bancarias"}


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


@tesoreria.get("/health")
async def health():
    return {"ok": True, "modulo": "tesoreria", "fase": 2}


# ---------------------------------------------------------------------------
# Movimientos de tesorería
# ---------------------------------------------------------------------------

class MovimientoTesoreria(BaseModel):
    cuenta_tipo: str  # caja | banco
    cuenta_id: str
    tipo: str  # ingreso | egreso
    fecha: str
    valor: float
    concepto: str
    tercero_id: str | None = None
    cuenta_contrapartida: str | None = None  # código PUC (p.ej. 4135, 5195)


async def _validar_cuenta(db, empresa_id: str, cuenta_tipo: str, cuenta_id: str) -> dict:
    if cuenta_tipo not in COLECCION_POR_TIPO:
        raise HTTPException(422, "cuenta_tipo debe ser 'caja' o 'banco'")
    doc = await db[COLECCION_POR_TIPO[cuenta_tipo]].find_one(
        {"_id": _oid(cuenta_id, "cuenta_id"), "empresa_id": empresa_id}
    )
    if not doc:
        raise HTTPException(404, "Cuenta de tesorería no encontrada")
    return doc


async def _asiento_tesoreria(
    db, empresa_id: str, empresa_cuenta_tipo: str, mov: dict, referencia: str,
    codigo_contrapartida: str | None,
) -> None:
    ahora = datetime.now(timezone.utc)
    cta_efectivo = await _cuenta_puc(db, empresa_id, CUENTA_PUC_POR_TIPO[empresa_cuenta_tipo])
    cta_contra = (
        await _cuenta_puc(db, empresa_id, codigo_contrapartida) if codigo_contrapartida else None
    )
    valor = round(mov["valor"], 2)
    es_ingreso = mov["tipo"] == "ingreso"

    def linea(cuenta, debito=0.0, credito=0.0):
        return {
            "empresa_id": empresa_id, "fecha": mov["fecha"], "cuenta_puc_id": cuenta,
            "tercero_id": mov.get("tercero_id"), "debito": round(debito, 2),
            "credito": round(credito, 2), "referencia": referencia, "fecha_creacion": ahora,
        }

    asientos = []
    if cta_efectivo:
        asientos.append(linea(cta_efectivo, debito=valor if es_ingreso else 0,
                              credito=0 if es_ingreso else valor))
    if cta_contra:
        asientos.append(linea(cta_contra, debito=0 if es_ingreso else valor,
                              credito=valor if es_ingreso else 0))
    if asientos:
        await db.asientos_contables.insert_many(asientos)


@tesoreria.get("/movimientos")
async def listar_movimientos(
    cuenta_tipo: str | None = Query(None),
    cuenta_id: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    db = get_db()
    filtro: dict = {"empresa_id": empresa_id}
    if cuenta_tipo:
        filtro["cuenta_tipo"] = cuenta_tipo
    if cuenta_id:
        filtro["cuenta_id"] = cuenta_id
    if desde and hasta:
        filtro["fecha"] = {"$gte": desde, "$lte": hasta}
    return [
        _serialize(d)
        async for d in db.movimientos_tesoreria.find(filtro).sort("fecha", -1)
    ]


@tesoreria.post("/movimientos", status_code=201)
async def crear_movimiento(
    payload: MovimientoTesoreria,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    db = get_db()
    if payload.tipo not in {"ingreso", "egreso"}:
        raise HTTPException(422, "tipo debe ser 'ingreso' o 'egreso'")
    if payload.valor <= 0:
        raise HTTPException(422, "El valor debe ser mayor a cero")
    cuenta = await _validar_cuenta(db, empresa_id, payload.cuenta_tipo, payload.cuenta_id)

    consecutivo = await db.movimientos_tesoreria.count_documents({"empresa_id": empresa_id}) + 1
    referencia = f"TES-{consecutivo}"
    doc = {
        **payload.model_dump(),
        "empresa_id": empresa_id,
        "consecutivo": consecutivo,
        "referencia": referencia,
        "cuenta_nombre": cuenta.get("nombre", ""),
        "origen": "manual",
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.movimientos_tesoreria.insert_one(doc)
    await _asiento_tesoreria(
        db, empresa_id, payload.cuenta_tipo, doc, referencia, payload.cuenta_contrapartida
    )
    return _serialize(await db.movimientos_tesoreria.find_one({"_id": res.inserted_id}))


async def _saldo_cuenta(db, empresa_id: str, cuenta_tipo: str, cuenta_id: str, base: float) -> float:
    saldo = base
    async for m in db.movimientos_tesoreria.find(
        {"empresa_id": empresa_id, "cuenta_tipo": cuenta_tipo, "cuenta_id": cuenta_id}
    ):
        saldo += m["valor"] if m["tipo"] == "ingreso" else -m["valor"]
    return round(saldo, 2)


async def _listar_cuentas(empresa_id: str, cuenta_tipo: str) -> list[dict]:
    db = get_db()
    salida = []
    async for c in db[COLECCION_POR_TIPO[cuenta_tipo]].find(
        {"empresa_id": empresa_id, "activo": {"$ne": False}}
    ):
        doc = _serialize(c)
        doc["saldo"] = await _saldo_cuenta(
            db, empresa_id, cuenta_tipo, doc["id"], float(doc.get("saldo_inicial", 0) or 0)
        )
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
# Cartera CxC / CxP con cruce de pagos
# ---------------------------------------------------------------------------

async def _cartera(empresa_id: str) -> dict:
    db = get_db()
    cxc, cxp = [], []
    async for f in db.facturas.find({"empresa_id": empresa_id}).sort("fecha", 1):
        total = float(f.get("total", 0))
        saldo = float(f.get("saldo_pendiente", total))
        if saldo <= 0.009:
            continue
        cxc.append({
            "id": str(f["_id"]), "tipo": "cxc",
            "documento": f"{f.get('prefijo','')}{f.get('consecutivo','')}",
            "tercero": f.get("cliente_nombre", ""), "tercero_id": f.get("cliente_id"),
            "fecha": f.get("fecha"), "total": round(total, 2), "saldo": round(saldo, 2),
        })
    async for f in db.facturas_proveedor.find({"empresa_id": empresa_id}).sort("fecha", 1):
        total = float(f.get("total_a_pagar", f.get("total", 0)))
        saldo = float(f.get("saldo_pendiente", total))
        if saldo <= 0.009:
            continue
        cxp.append({
            "id": str(f["_id"]), "tipo": "cxp",
            "documento": f.get("numero_factura", ""),
            "tercero": f.get("proveedor_nombre", ""), "tercero_id": f.get("proveedor_id"),
            "fecha": f.get("fecha"), "total": round(total, 2), "saldo": round(saldo, 2),
        })
    return {
        "cxc": cxc, "cxp": cxp,
        "resumen": {
            "total_cxc": round(sum(d["saldo"] for d in cxc), 2),
            "total_cxp": round(sum(d["saldo"] for d in cxp), 2),
        },
    }


@tesoreria.get("/cxc-cxp")
async def cxc_cxp(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    return await _cartera(empresa_id)


class PagoCrear(BaseModel):
    documento_tipo: str  # cxc | cxp
    documento_id: str
    cuenta_tipo: str  # caja | banco
    cuenta_id: str
    fecha: str
    valor: float
    observaciones: str | None = None


@tesoreria.get("/pagos")
async def listar_pagos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("tesoreria", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.pagos.find({"empresa_id": empresa_id}).sort("fecha", -1)]


@tesoreria.post("/pagos", status_code=201)
async def registrar_pago(
    payload: PagoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("tesoreria", "crear")),
):
    """Cruza un recaudo (cxc) o un pago a proveedor (cxp) contra su factura."""
    db = get_db()
    if payload.documento_tipo not in {"cxc", "cxp"}:
        raise HTTPException(422, "documento_tipo debe ser 'cxc' o 'cxp'")
    if payload.valor <= 0:
        raise HTTPException(422, "El valor debe ser mayor a cero")
    cuenta = await _validar_cuenta(db, empresa_id, payload.cuenta_tipo, payload.cuenta_id)

    coleccion = "facturas" if payload.documento_tipo == "cxc" else "facturas_proveedor"
    doc_oid = _oid(payload.documento_id, "documento_id")
    factura = await db[coleccion].find_one({"_id": doc_oid, "empresa_id": empresa_id})
    if not factura:
        raise HTTPException(404, "Documento no encontrado")

    total = float(
        factura.get("total_a_pagar", factura.get("total", 0))
        if payload.documento_tipo == "cxp" else factura.get("total", 0)
    )
    saldo = float(factura.get("saldo_pendiente", total))
    if payload.valor > saldo + 0.009:
        raise HTTPException(409, f"El valor supera el saldo pendiente ({saldo})")
    nuevo_saldo = round(saldo - payload.valor, 2)

    consecutivo = await db.pagos.count_documents({"empresa_id": empresa_id}) + 1
    referencia = f"{'RC' if payload.documento_tipo == 'cxc' else 'CE'}-{consecutivo}"
    tercero_id = factura.get("cliente_id") if payload.documento_tipo == "cxc" else factura.get("proveedor_id")

    pago = {
        **payload.model_dump(),
        "empresa_id": empresa_id,
        "consecutivo": consecutivo,
        "referencia": referencia,
        "tercero_id": tercero_id,
        "tercero_nombre": factura.get("cliente_nombre") or factura.get("proveedor_nombre", ""),
        "documento_numero": (
            f"{factura.get('prefijo','')}{factura.get('consecutivo','')}"
            if payload.documento_tipo == "cxc" else factura.get("numero_factura", "")
        ),
        "saldo_resultante": nuevo_saldo,
        "cuenta_nombre": cuenta.get("nombre", ""),
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.pagos.insert_one(pago)

    await db[coleccion].update_one(
        {"_id": doc_oid},
        {"$set": {"saldo_pendiente": nuevo_saldo,
                  "estado": "pagada" if nuevo_saldo <= 0.009 else "parcial"}},
    )

    # Movimiento de tesorería asociado
    mov = {
        "empresa_id": empresa_id,
        "cuenta_tipo": payload.cuenta_tipo,
        "cuenta_id": payload.cuenta_id,
        "cuenta_nombre": cuenta.get("nombre", ""),
        "tipo": "ingreso" if payload.documento_tipo == "cxc" else "egreso",
        "fecha": payload.fecha,
        "valor": payload.valor,
        "concepto": f"{'Recaudo' if payload.documento_tipo == 'cxc' else 'Pago'} {pago['documento_numero']}",
        "tercero_id": tercero_id,
        "referencia": referencia,
        "origen": "cruce_cartera",
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    await db.movimientos_tesoreria.insert_one(mov)

    # Asiento: contrapartida = clientes (1305) o proveedores (2205)
    await _asiento_tesoreria(
        db, empresa_id, payload.cuenta_tipo, mov, referencia,
        "1305" if payload.documento_tipo == "cxc" else "2205",
    )
    return _serialize(await db.pagos.find_one({"_id": res.inserted_id}))


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
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}}
    ):
        clave = "ingresos" if m["tipo"] == "ingreso" else "egresos"
        por_dia[m["fecha"]][clave] += float(m.get("valor", 0))

    filas, acumulado = [], 0.0
    for fecha in sorted(por_dia):
        ing = round(por_dia[fecha]["ingresos"], 2)
        egr = round(por_dia[fecha]["egresos"], 2)
        acumulado += ing - egr
        filas.append({"fecha": fecha, "ingresos": ing, "egresos": egr,
                      "neto": round(ing - egr, 2), "acumulado": round(acumulado, 2)})

    total_ing = round(sum(f["ingresos"] for f in filas), 2)
    total_egr = round(sum(f["egresos"] for f in filas), 2)
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
                    "neto": round(total_ing - total_egr, 2)},
    }


@tesoreria.get("/conciliacion-bancaria-auto")
async def conciliacion_auto():
    raise HTTPException(501, _F3)


router.include_router(tesoreria)

# Catálogos de cuentas de tesorería
router.include_router(
    crud_router(
        prefix="/api/tesoreria/cuentas-caja",
        coleccion="cajas",
        modulo_permiso="tesoreria",
        tags=["tesoreria:caja"],
    )
)
router.include_router(
    crud_router(
        prefix="/api/tesoreria/cuentas-bancarias",
        coleccion="cuentas_bancarias",
        modulo_permiso="tesoreria",
        tags=["tesoreria:bancos"],
    )
)
