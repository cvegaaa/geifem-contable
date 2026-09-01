"""Facturación FASE 1: CRUD estructurado de facturas + consecutivo DIAN + asiento contable espejo.

La validación/envío real a DIAN (CUFE + XML) se conecta con el ClientePT
en fases posteriores. Fase 1 permite registrar la factura con items,
calcular IVA, asignar consecutivo desde la resolución y generar el
asiento contable espejo mínimo.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth.dependencies import get_empresa_activa, require_permiso, get_current_user
from core.dian.cliente_pt import get_cliente_pt
from db import get_db

router = APIRouter(prefix="/api/facturacion", tags=["facturacion"])


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class ItemFactura(BaseModel):
    producto_id: str
    cantidad: float
    precio_unitario: float
    tarifa_iva: float = 0  # porcentaje: 0, 5, 19, etc.


class FacturaCrear(BaseModel):
    cliente_id: str
    resolucion_id: str
    fecha: str
    forma_pago_id: str | None = None
    items: list[ItemFactura] = Field(min_length=1)
    observaciones: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _buscar_cuenta_puc(db, empresa_id: str, codigo: str) -> str | None:
    """Devuelve el _id (str) de una cuenta PUC por código dentro del plan de la empresa."""
    doc = await db.plan_cuentas.find_one({"empresa_id": empresa_id, "codigo": codigo})
    return str(doc["_id"]) if doc else None


async def _generar_asiento_espejo(
    db, empresa_id: str, factura_id: str, fecha: str,
    cliente_id: str, subtotal: float, iva_total: float, total: float,
) -> None:
    """Crea registros en asientos_contables que reflejan la factura.

    Asiento mínimo (Fase 1):
      Débito  1305 Clientes       — total
      Crédito 4135 Ingresos       — subtotal
      Crédito 2408 IVA por pagar  — iva_total (si > 0 y la cuenta existe)

    En Fase 2 se refinará según forma de pago (contado → Caja/Bancos).
    """
    cuenta_clientes = await _buscar_cuenta_puc(db, empresa_id, "1305")
    cuenta_ingresos = await _buscar_cuenta_puc(db, empresa_id, "4135")
    cuenta_iva = await _buscar_cuenta_puc(db, empresa_id, "2408")

    ref = f"FACT-{factura_id}"
    ahora = datetime.now(timezone.utc)
    asientos = []

    if cuenta_clientes:
        asientos.append({
            "empresa_id": empresa_id, "fecha": fecha,
            "cuenta_puc_id": cuenta_clientes, "tercero_id": cliente_id,
            "debito": round(total, 2), "credito": 0,
            "referencia": ref, "fecha_creacion": ahora,
        })
    if cuenta_ingresos:
        asientos.append({
            "empresa_id": empresa_id, "fecha": fecha,
            "cuenta_puc_id": cuenta_ingresos, "tercero_id": cliente_id,
            "debito": 0, "credito": round(subtotal, 2),
            "referencia": ref, "fecha_creacion": ahora,
        })
    if iva_total > 0 and cuenta_iva:
        asientos.append({
            "empresa_id": empresa_id, "fecha": fecha,
            "cuenta_puc_id": cuenta_iva, "tercero_id": cliente_id,
            "debito": 0, "credito": round(iva_total, 2),
            "referencia": ref, "fecha_creacion": ahora,
        })

    if asientos:
        await db.asientos_contables.insert_many(asientos)


# ---------------------------------------------------------------------------
# Endpoints — Facturas
# ---------------------------------------------------------------------------

@router.get("/facturas")
async def listar_facturas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    db = get_db()
    return [
        _serialize(d)
        async for d in db.facturas.find({"empresa_id": empresa_id}).sort("fecha", -1)
    ]


@router.post("/facturas", status_code=201)
async def crear_factura(
    payload: FacturaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()

    # --- Validar cliente ---
    try:
        cliente_oid = ObjectId(payload.cliente_id)
    except Exception:
        raise HTTPException(400, "cliente_id inválido")
    cliente = await db.terceros.find_one(
        {"_id": cliente_oid, "empresa_id": empresa_id, "activo": {"$ne": False}}
    )
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    # --- Validar resolución y obtener consecutivo ---
    try:
        res_oid = ObjectId(payload.resolucion_id)
    except Exception:
        raise HTTPException(400, "resolucion_id inválido")
    resolucion = await db.resoluciones_dian.find_one(
        {"_id": res_oid, "empresa_id": empresa_id, "activo": {"$ne": False}}
    )
    if not resolucion:
        raise HTTPException(404, "Resolución DIAN no encontrada o inactiva")

    actual = resolucion.get("consecutivo_actual", resolucion["rango_desde"] - 1)
    siguiente = actual + 1
    if siguiente > resolucion["rango_hasta"]:
        raise HTTPException(409, "Rango DIAN agotado para esta resolución")

    # --- Calcular totales por línea ---
    items_calc = []
    subtotal = 0.0
    iva_total = 0.0
    for item in payload.items:
        if item.cantidad <= 0:
            raise HTTPException(422, "La cantidad debe ser mayor a cero")
        if item.precio_unitario < 0:
            raise HTTPException(422, "El precio unitario no puede ser negativo")
        linea_subtotal = item.cantidad * item.precio_unitario
        linea_iva = linea_subtotal * (item.tarifa_iva / 100)
        items_calc.append({
            "producto_id": item.producto_id,
            "cantidad": item.cantidad,
            "precio_unitario": item.precio_unitario,
            "tarifa_iva": item.tarifa_iva,
            "subtotal": round(linea_subtotal, 2),
            "iva": round(linea_iva, 2),
            "total": round(linea_subtotal + linea_iva, 2),
        })
        subtotal += linea_subtotal
        iva_total += linea_iva

    total = subtotal + iva_total

    # --- Actualizar consecutivo de la resolución ---
    await db.resoluciones_dian.update_one(
        {"_id": resolucion["_id"]},
        {"$set": {"consecutivo_actual": siguiente}},
    )

    # --- Crear factura ---
    doc = {
        "empresa_id": empresa_id,
        "cliente_id": payload.cliente_id,
        "cliente_nombre": cliente.get("nombre", ""),
        "resolucion_id": payload.resolucion_id,
        "prefijo": resolucion["prefijo"],
        "consecutivo": siguiente,
        "fecha": payload.fecha,
        "forma_pago_id": payload.forma_pago_id,
        "items": items_calc,
        "subtotal": round(subtotal, 2),
        "iva_total": round(iva_total, 2),
        "total": round(total, 2),
        "observaciones": payload.observaciones,
        "estado_dian": "borrador",
        "cufe": None,
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    result = await db.facturas.insert_one(doc)
    factura_id = str(result.inserted_id)

    # --- Asiento contable espejo ---
    await _generar_asiento_espejo(
        db, empresa_id, factura_id, payload.fecha,
        payload.cliente_id, subtotal, iva_total, total,
    )

    return _serialize(await db.facturas.find_one({"_id": result.inserted_id}))


@router.get("/facturas/{fid}")
async def obtener_factura(
    fid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    db = get_db()
    try:
        oid = ObjectId(fid)
    except Exception:
        raise HTTPException(400, "id inválido")
    doc = await db.facturas.find_one({"_id": oid, "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Factura no encontrada")
    return _serialize(doc)


@router.post("/facturas/{fid}/enviar-dian")
async def enviar_dian(
    fid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "editar")),
):
    """Stub Fase 1: llama al ClientePT (no configurado). Deja el contrato listo."""
    db = get_db()
    try:
        oid = ObjectId(fid)
    except Exception:
        raise HTTPException(400, "id inválido")
    factura = await db.facturas.find_one({"_id": oid, "empresa_id": empresa_id})
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    pt = get_cliente_pt()
    try:
        resultado = await pt.enviar_factura(empresa_id, factura)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))
    await db.facturas.update_one({"_id": oid}, {"$set": resultado})
    return {"ok": True, **resultado}


# ---------------------------------------------------------------------------
# Sub-recursos: documento-equivalente-pos y notas-credito-debito (stubs Fase 1)
# ---------------------------------------------------------------------------

@router.get("/documento-equivalente-pos")
async def listar_pos(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.documentos_pos.find({"empresa_id": empresa_id})]


@router.get("/notas-credito-debito")
async def listar_notas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("facturacion", "leer")),
):
    db = get_db()
    return [_serialize(d) async for d in db.notas_credito_debito.find({"empresa_id": empresa_id})]


# ---------------------------------------------------------------------------
# Notas crédito / débito — FASE 1
# ---------------------------------------------------------------------------

class ItemNota(BaseModel):
    descripcion: str
    cantidad: float = 1
    precio_unitario: float
    tarifa_iva: float = 0


class NotaCrear(BaseModel):
    factura_id: str
    tipo: str = Field(pattern="^(credito|debito)$")
    fecha: str
    motivo: str
    items: list[ItemNota] = Field(min_length=1)


async def _asiento_nota(
    db, empresa_id: str, nota_id: str, tipo: str, fecha: str,
    cliente_id: str | None, subtotal: float, iva_total: float, total: float,
) -> None:
    """Asiento espejo de la nota.

    Nota crédito = reverso de la venta (débito a ingresos/IVA, crédito a clientes).
    Nota débito  = mismo sentido que la factura.
    """
    ahora = datetime.now(timezone.utc)
    ref = f"NOTA-{tipo.upper()}-{nota_id}"
    cta_clientes = await _buscar_cuenta_puc(db, empresa_id, "1305")
    cta_ingresos = await _buscar_cuenta_puc(db, empresa_id, "4135")
    cta_iva = await _buscar_cuenta_puc(db, empresa_id, "2408")
    signo = -1 if tipo == "credito" else 1

    def linea(cuenta, debito, credito):
        return {
            "empresa_id": empresa_id, "fecha": fecha, "cuenta_puc_id": cuenta,
            "tercero_id": cliente_id,
            "debito": round(max(debito, 0), 2), "credito": round(max(credito, 0), 2),
            "referencia": ref, "fecha_creacion": ahora,
        }

    asientos = []
    if cta_clientes:
        asientos.append(linea(cta_clientes, total if signo > 0 else 0, total if signo < 0 else 0))
    if cta_ingresos:
        asientos.append(linea(cta_ingresos, subtotal if signo < 0 else 0, subtotal if signo > 0 else 0))
    if iva_total > 0 and cta_iva:
        asientos.append(linea(cta_iva, iva_total if signo < 0 else 0, iva_total if signo > 0 else 0))
    if asientos:
        await db.asientos_contables.insert_many(asientos)


@router.post("/notas-credito-debito", status_code=201)
async def crear_nota(
    payload: NotaCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()
    try:
        oid = ObjectId(payload.factura_id)
    except Exception:
        raise HTTPException(400, "factura_id inválido")
    factura = await db.facturas.find_one({"_id": oid, "empresa_id": empresa_id})
    if not factura:
        raise HTTPException(404, "Factura origen no encontrada")

    subtotal = 0.0
    iva_total = 0.0
    items = []
    for it in payload.items:
        if it.cantidad <= 0 or it.precio_unitario < 0:
            raise HTTPException(422, "Cantidad o precio inválido")
        ls = it.cantidad * it.precio_unitario
        li = ls * (it.tarifa_iva / 100)
        items.append({**it.model_dump(), "subtotal": round(ls, 2), "iva": round(li, 2),
                      "total": round(ls + li, 2)})
        subtotal += ls
        iva_total += li
    total = subtotal + iva_total

    consecutivo = await db.notas_credito_debito.count_documents(
        {"empresa_id": empresa_id, "tipo": payload.tipo}
    ) + 1
    doc = {
        "empresa_id": empresa_id,
        "tipo": payload.tipo,
        "prefijo": "NC" if payload.tipo == "credito" else "ND",
        "consecutivo": consecutivo,
        "factura_id": payload.factura_id,
        "factura_numero": f"{factura.get('prefijo','')}{factura.get('consecutivo','')}",
        "cliente_id": factura.get("cliente_id"),
        "cliente_nombre": factura.get("cliente_nombre", ""),
        "fecha": payload.fecha,
        "motivo": payload.motivo,
        "items": items,
        "subtotal": round(subtotal, 2),
        "iva_total": round(iva_total, 2),
        "total": round(total, 2),
        "estado_dian": "borrador",
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.notas_credito_debito.insert_one(doc)
    await _asiento_nota(db, empresa_id, str(res.inserted_id), payload.tipo, payload.fecha,
                        factura.get("cliente_id"), subtotal, iva_total, total)
    return _serialize(await db.notas_credito_debito.find_one({"_id": res.inserted_id}))


# ---------------------------------------------------------------------------
# Documento equivalente POS — FASE 1
# ---------------------------------------------------------------------------

class ItemPos(BaseModel):
    producto_id: str | None = None
    descripcion: str
    cantidad: float = 1
    precio_unitario: float
    tarifa_iva: float = 0


class PosCrear(BaseModel):
    fecha: str
    cliente_id: str | None = None
    forma_pago_id: str | None = None
    items: list[ItemPos] = Field(min_length=1)
    observaciones: str | None = None


@router.post("/documento-equivalente-pos", status_code=201)
async def crear_pos(
    payload: PosCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("facturacion", "crear")),
):
    db = get_db()
    subtotal = 0.0
    iva_total = 0.0
    items = []
    for it in payload.items:
        if it.cantidad <= 0 or it.precio_unitario < 0:
            raise HTTPException(422, "Cantidad o precio inválido")
        ls = it.cantidad * it.precio_unitario
        li = ls * (it.tarifa_iva / 100)
        items.append({**it.model_dump(), "subtotal": round(ls, 2), "iva": round(li, 2),
                      "total": round(ls + li, 2)})
        subtotal += ls
        iva_total += li
    total = subtotal + iva_total

    consecutivo = await db.documentos_pos.count_documents({"empresa_id": empresa_id}) + 1
    doc = {
        "empresa_id": empresa_id,
        "prefijo": "POS",
        "consecutivo": consecutivo,
        "fecha": payload.fecha,
        "cliente_id": payload.cliente_id,
        "forma_pago_id": payload.forma_pago_id,
        "items": items,
        "subtotal": round(subtotal, 2),
        "iva_total": round(iva_total, 2),
        "total": round(total, 2),
        "observaciones": payload.observaciones,
        "creado_por": usuario["id"],
        "fecha_creacion": datetime.now(timezone.utc),
    }
    res = await db.documentos_pos.insert_one(doc)
    await _generar_asiento_espejo(
        db, empresa_id, str(res.inserted_id), payload.fecha,
        payload.cliente_id or "", subtotal, iva_total, total,
    )
    return _serialize(await db.documentos_pos.find_one({"_id": res.inserted_id}))
