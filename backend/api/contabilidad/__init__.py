"""Contabilidad: comprobantes manuales (ajuste, nota, apertura, cierre) y auditoría.

Un comprobante en estado `contabilizado` escribe sus líneas en el libro
(`asientos_contables`), de donde salen todos los reportes contables. En
`borrador` no afecta el libro.
"""
from typing import Literal

import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from core import cartera
from core.aprobaciones import puede_aprobar, requiere_aprobacion
from core.auth.dependencies import get_current_user, get_empresa_activa, require_permiso
from core.documentos import (
    NOMBRES_DOCUMENTO,
    Linea,
    auditar,
    borrar_asientos,
    campos_conservados,
    cargar_editable,
    en_transaccion,
    fecha_cierre,
    formatear_numero,
    marca_anulacion,
    oid,
    registrar_asientos,
    serializar,
    siguiente_consecutivo,
    ahora,
)
from db import get_db
from core.dinero import centavos

router = APIRouter(prefix="/api/contabilidad", tags=["contabilidad"])

TipoComprobante = Literal["ajuste", "nota", "apertura", "cierre"]
PREFIJOS = {"ajuste": "CA", "nota": "NT", "apertura": "AP", "cierre": "CC"}
DOC_TIPO = "comprobante"


class LineaComprobante(BaseModel):
    cuenta_puc_id: str
    debito: float = Field(default=0, ge=0)
    credito: float = Field(default=0, ge=0)
    tercero_id: str | None = None
    descripcion: str | None = None
    # Solo en la apertura: detalle de las cuentas por cobrar y por pagar (documento, fecha y vencimiento).
    documento_numero: str | None = None
    fecha_documento: str | None = None
    fecha_vencimiento: str | None = None

    @model_validator(mode="after")
    def _un_lado(self):
        if bool(self.debito) == bool(self.credito):
            raise ValueError("Cada línea debe tener valor en débito o en crédito (no ambos)")
        return self


class ComprobanteCrear(BaseModel):
    tipo: TipoComprobante
    fecha: str
    tercero_id: str | None = None
    lineas: list[LineaComprobante] = Field(min_length=2)
    descripcion: str | None = None
    estado: Literal["borrador", "contabilizado"] = "borrador"


class Rechazo(BaseModel):
    motivo: str = Field(min_length=3)


class Anulacion(BaseModel):
    motivo: str | None = None


def _validar_cuadre(payload: ComprobanteCrear) -> None:
    deb = sum(centavos(l.debito) for l in payload.lineas)
    cre = sum(centavos(l.credito) for l in payload.lineas)
    if deb != cre:
        raise HTTPException(422, f"Comprobante descuadrado: débitos {deb / 100:,.2f} ≠ créditos {cre / 100:,.2f}")


async def _aplicar(empresa_id: str, doc_id: str, doc: dict, s) -> None:
    # La apertura detalla la cartera por documento; se mantiene al día con el comprobante.
    await cartera.sincronizar_apertura(empresa_id, doc_id, doc, s)
    if doc["estado"] != "contabilizado":
        return
    lineas = [
        Linea(
            cuenta_id=l["cuenta_puc_id"], debito=l["debito"], credito=l["credito"],
            tercero_id=l.get("tercero_id") or doc.get("tercero_id"),
            descripcion=l.get("descripcion") or doc.get("descripcion"),
        )
        for l in doc["lineas"]
    ]
    await registrar_asientos(empresa_id, DOC_TIPO, doc_id, doc["numero"], doc["fecha"], lineas, s)


@router.post("/comprobantes", status_code=201)
async def crear_comprobante(
    payload: ComprobanteCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "crear")),
):
    _validar_cuadre(payload)
    db = get_db()
    # Quien requiere aprobación deja el comprobante «por aprobar»: no llega al libro hasta que lo autoricen.
    estado = "por_aprobar" if payload.estado == "contabilizado" and requiere_aprobacion(usuario) else payload.estado

    async def _tx(s):
        prefijo = PREFIJOS[payload.tipo]
        consecutivo = await siguiente_consecutivo(empresa_id, f"comprobante:{payload.tipo}", s)
        doc = {
            **payload.model_dump(),
            "estado": estado,
            "empresa_id": empresa_id,
            "prefijo": prefijo,
            "consecutivo": consecutivo,
            "numero": formatear_numero(prefijo, consecutivo),
            "creado_por": usuario["id"],
            "fecha_creacion": ahora(),
        }
        res = await db.comprobantes_contables.insert_one(doc, session=s)
        doc_id = str(res.inserted_id)
        await _aplicar(empresa_id, doc_id, doc, s)
        await auditar(empresa_id, DOC_TIPO, doc_id, doc["numero"], usuario["id"], "creado", s, {"estado": estado})
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": nuevo}))


@router.get("/comprobantes")
async def consultar_comprobantes(
    tipo: str | None = None,
    estado: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if tipo:
        filtro["tipo"] = tipo
    if estado:
        filtro["estado"] = estado
    if desde or hasta:
        filtro["fecha"] = {}
        if desde:
            filtro["fecha"]["$gte"] = desde
        if hasta:
            filtro["fecha"]["$lte"] = hasta
    cursor = get_db().comprobantes_contables.find(filtro).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.get("/comprobantes/{cid}")
async def obtener_comprobante(
    cid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    doc = await get_db().comprobantes_contables.find_one({"_id": oid(cid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "No encontrado")
    return serializar(doc)


@router.put("/comprobantes/{cid}")
async def editar_comprobante(
    cid: str,
    payload: ComprobanteCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "editar")),
):
    _validar_cuadre(payload)
    db = get_db()
    estado = "por_aprobar" if payload.estado == "contabilizado" and requiere_aprobacion(usuario) else payload.estado

    async def _tx(s):
        existente = await cargar_editable("comprobantes_contables", empresa_id, cid, s)
        if payload.tipo != existente["tipo"]:
            raise HTTPException(409, "No se puede cambiar el tipo de un comprobante ya numerado")
        await borrar_asientos(empresa_id, DOC_TIPO, cid, s)
        doc = {
            **payload.model_dump(),
            "estado": estado,
            **campos_conservados(existente),
            "editado_por": usuario["id"],
            "fecha_actualizacion": ahora(),
        }
        await db.comprobantes_contables.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar(empresa_id, cid, doc, s)
        await auditar(empresa_id, DOC_TIPO, cid, doc["numero"], usuario["id"], "editado", s, {"estado": estado})

    await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": oid(cid)}))


@router.post("/comprobantes/{cid}/aprobar")
async def aprobar_comprobante(
    cid: str,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "leer")),
):
    """Autoriza un comprobante «por aprobar»: se contabiliza y queda registrado quién lo aprobó."""
    if not puede_aprobar(usuario):
        raise HTTPException(403, "No tienes permiso para aprobar comprobantes")
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("comprobantes_contables", empresa_id, cid, s)
        if existente["estado"] != "por_aprobar":
            raise HTTPException(409, "El comprobante no está pendiente de aprobación")
        if existente.get("creado_por") == usuario["id"] and requiere_aprobacion(usuario):
            raise HTTPException(403, "No puedes aprobar un comprobante que tú mismo registraste")
        doc = {**existente, "estado": "contabilizado", "aprobado_por": usuario["id"], "aprobado_en": ahora()}
        doc.pop("rechazado_por", None)
        doc.pop("motivo_rechazo", None)
        await db.comprobantes_contables.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar(empresa_id, cid, doc, s)
        await auditar(empresa_id, DOC_TIPO, cid, doc["numero"], usuario["id"], "aprobado", s)

    await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": oid(cid)}))


@router.post("/comprobantes/{cid}/rechazar")
async def rechazar_comprobante(
    cid: str,
    payload: Rechazo,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "leer")),
):
    """Devuelve un comprobante «por aprobar» a quien lo registró, con el motivo; no toca el libro."""
    if not puede_aprobar(usuario):
        raise HTTPException(403, "No tienes permiso para aprobar comprobantes")
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("comprobantes_contables", empresa_id, cid, s)
        if existente["estado"] != "por_aprobar":
            raise HTTPException(409, "El comprobante no está pendiente de aprobación")
        await db.comprobantes_contables.update_one(
            {"_id": existente["_id"]},
            {"$set": {"estado": "rechazado", "rechazado_por": usuario["id"], "motivo_rechazo": payload.motivo}}, session=s)
        await auditar(empresa_id, DOC_TIPO, cid, existente["numero"], usuario["id"], "rechazado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": oid(cid)}))


@router.post("/comprobantes/{cid}/anular")
async def anular_comprobante(
    cid: str,
    payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("comprobantes_contables", empresa_id, cid, s)
        await borrar_asientos(empresa_id, DOC_TIPO, cid, s)
        await cartera.sincronizar_apertura(empresa_id, cid, {**existente, "estado": "anulado"}, s)
        await db.comprobantes_contables.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s
        )
        await auditar(empresa_id, DOC_TIPO, cid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": oid(cid)}))


# ---------------------------------------------------------------------------
# Cierre de periodos
# ---------------------------------------------------------------------------

class CierreEntrada(BaseModel):
    fecha_cierre: str | None = Field(
        default=None, description="Último día cerrado (fin de mes, AAAA-MM-DD). Vacío = reabrir todo.")
    motivo: str | None = None


@router.get("/cierre")
async def ver_cierre(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    db = get_db()
    historial = [
        serializar(d) async for d in db.auditoria.find(
            {"empresa_id": empresa_id, "documento_tipo": "cierre_periodo"}).sort("fecha_hora", -1).limit(20)
    ]
    return {"fecha_cierre": await fecha_cierre(empresa_id), "historial": historial}


@router.put("/cierre")
async def definir_cierre(
    payload: CierreEntrada,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("contabilidad", "editar")),
):
    """Cierra la contabilidad hasta una fecha (fin de mes) o la reabre.

    Hacia adelante lo puede hacer quien tenga permiso de edición; reabrir (mover la fecha hacia
    atrás) exige un administrador y deja constancia con su motivo.
    """
    db = get_db()
    nueva = payload.fecha_cierre or None
    actual = await fecha_cierre(empresa_id)
    if nueva:
        try:
            d = date.fromisoformat(nueva)
        except ValueError:
            raise HTTPException(422, "Fecha inválida (usa AAAA-MM-DD)")
        if (d + timedelta(days=1)).day != 1:
            raise HTTPException(422, "El cierre debe ser el último día de un mes")
        if d >= date.today():
            raise HTTPException(422, "No se puede cerrar un periodo que aún no ha terminado")
        borradores = await db.comprobantes_contables.count_documents(
            {"empresa_id": empresa_id, "estado": {"$in": ["borrador", "por_aprobar"]}, "fecha": {"$lte": nueva}})
        if borradores:
            raise HTTPException(
                409, f"Hay {borradores} comprobante(s) en borrador con fecha dentro del periodo: contabilízalos o anúlalos antes de cerrar.")
    reabre = (actual and not nueva) or (actual and nueva and nueva < actual)
    if reabre:
        if usuario.get("rol") != "admin":
            raise HTTPException(403, "Solo un administrador puede reabrir un periodo cerrado")
        if not (payload.motivo or "").strip():
            raise HTTPException(422, "Indica el motivo para reabrir el periodo")
    await db.empresas.update_one(
        {"_id": oid(empresa_id)},
        {"$set": {"fecha_cierre": nueva}} if nueva else {"$unset": {"fecha_cierre": ""}})
    await auditar(empresa_id, "cierre_periodo", empresa_id, nueva or "abierto", usuario["id"],
                  "reabierto" if reabre else "cerrado", None, {"anterior": actual, "motivo": payload.motivo})
    return await ver_cierre(empresa_id)


@router.get("/usuarios-nombres")
async def nombres_de_usuarios(
    ids: str = Query("", description="Ids separados por coma"),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(get_current_user),
):
    """Nombre de los usuarios de la empresa (para mostrar quién elaboró o aprobó un documento)."""
    lista = [oid(i) for i in ids.split(",") if i.strip()][:100]
    cursor = get_db().usuarios.find({"_id": {"$in": lista}, "empresa_ids": empresa_id}, {"nombre": 1})
    return {str(u["_id"]): u.get("nombre", "") async for u in cursor}


@router.get("/firmas/{documento_id}")
async def firmas_de_documento(
    documento_id: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(get_current_user),
):
    """Quién elaboró y quién aprobó un documento (cualquier módulo), según la auditoría."""
    db = get_db()
    base = {"empresa_id": empresa_id, "documento_id": documento_id}
    creado = await db.auditoria.find_one({**base, "accion": "creado"}, sort=[("fecha_hora", 1)])
    aprobado = await db.auditoria.find_one({**base, "accion": "aprobado"}, sort=[("fecha_hora", -1)])
    nombres = await _nombres(empresa_id, {(creado or {}).get("usuario_id"), (aprobado or {}).get("usuario_id")})
    return {"elaboro": nombres.get((creado or {}).get("usuario_id", ""), ""),
            "aprobo": nombres.get((aprobado or {}).get("usuario_id", ""), "")}


async def _nombres(empresa_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    cursor = get_db().usuarios.find({"_id": {"$in": [oid(i) for i in ids]}}, {"nombre": 1})
    return {str(u["_id"]): u.get("nombre", "") async for u in cursor}


@router.get("/auditoria")
async def listar_auditoria(
    documento_id: str | None = Query(None),
    documento_tipo: str | None = Query(None),
    accion: str | None = Query(None),
    usuario_id: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    q: str | None = Query(None, description="Texto en el número del documento"),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if documento_id:
        filtro["documento_id"] = documento_id
    if documento_tipo:
        filtro["documento_tipo"] = documento_tipo
    if accion:
        filtro["accion"] = accion
    if usuario_id:
        filtro["usuario_id"] = usuario_id
    if q:
        filtro["numero"] = {"$regex": re.escape(q), "$options": "i"}
    if desde or hasta:
        rango = {}
        if desde:
            rango["$gte"] = datetime.fromisoformat(desde).replace(tzinfo=timezone.utc)
        if hasta:
            rango["$lt"] = datetime.fromisoformat(hasta).replace(tzinfo=timezone.utc) + timedelta(days=1)
        filtro["fecha_hora"] = rango
    filas = [serializar(d) async for d in get_db().auditoria.find(filtro).sort("fecha_hora", -1).limit(500)]
    nombres = await _nombres(empresa_id, {f["usuario_id"] for f in filas})
    for f in filas:
        f["usuario_nombre"] = nombres.get(f["usuario_id"], "")
        f["documento_nombre"] = NOMBRES_DOCUMENTO.get(f["documento_tipo"], (f["documento_tipo"], None))[0]
    return filas


# ---------------------------------------------------------------------------
# Estado de los periodos (meses y años)
# ---------------------------------------------------------------------------

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


@router.get("/cierre/periodos")
async def estado_periodos(
    anio: int | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    """Meses del año con su estado (abierto, cerrado o futuro) y resumen de todos los años con movimiento."""
    db = get_db()
    cierre = await fecha_cierre(empresa_id)
    hoy = date.today()
    anio = anio or hoy.year
    por_mes = {}
    async for g in await db.asientos_contables.aggregate([
        {"$match": {"empresa_id": empresa_id, "fecha": {"$gte": f"{anio}-01-01", "$lte": f"{anio}-12-31"}}},
        {"$group": {"_id": {"$substr": ["$fecha", 0, 7]}, "documentos": {"$addToSet": "$documento_id"}}},
    ]):
        por_mes[g["_id"]] = len(g["documentos"])
    pendientes = defaultdict(int)
    async for c in db.comprobantes_contables.find(
        {"empresa_id": empresa_id, "estado": {"$in": ["borrador", "por_aprobar"]},
         "fecha": {"$gte": f"{anio}-01-01", "$lte": f"{anio}-12-31"}}, {"fecha": 1}):
        pendientes[c["fecha"][:7]] += 1
    meses = []
    for m in range(1, 13):
        ini = date(anio, m, 1)
        fin = date(anio, m, calendar.monthrange(anio, m)[1])
        clave = f"{anio}-{m:02d}"
        estado = "futuro" if ini > hoy else ("cerrado" if cierre and fin.isoformat() <= cierre else "abierto")
        meses.append({"mes": m, "nombre": MESES[m - 1], "fin": fin.isoformat(), "estado": estado,
                      "documentos": por_mes.get(clave, 0), "pendientes": pendientes.get(clave, 0)})
    primero = await db.asientos_contables.find_one({"empresa_id": empresa_id}, sort=[("fecha", 1)])
    desde = int(primero["fecha"][:4]) if primero else hoy.year
    anios = []
    for a in range(max(desde, hoy.year - 10), hoy.year + 1):
        if cierre and cierre >= f"{a}-12-31":
            est = "cerrado"
        elif cierre and cierre >= f"{a}-01-31":
            est = "parcial"
        else:
            est = "abierto"
        anios.append({"anio": a, "estado": est})
    return {"anio": anio, "fecha_cierre": cierre, "meses": meses, "anios": anios}


# ---------------------------------------------------------------------------
# Consulta unificada: todos los documentos que llegaron al libro
# ---------------------------------------------------------------------------

@router.get("/documentos")
async def consultar_documentos(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    tipo: str | None = Query(None, description="documento_tipo"),
    q: str | None = Query(None, description="Texto en el número"),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    """Un renglón por documento de cualquier módulo (ventas, compras, tesorería, inventario, nómina…) con su asiento."""
    db = get_db()
    match: dict = {"empresa_id": empresa_id}
    if desde or hasta:
        match["fecha"] = {}
        if desde:
            match["fecha"]["$gte"] = desde
        if hasta:
            match["fecha"]["$lte"] = hasta
    if tipo:
        match["documento_tipo"] = tipo
    if q:
        match["referencia"] = {"$regex": re.escape(q), "$options": "i"}
    filas = []
    async for g in await db.asientos_contables.aggregate([
        {"$match": match},
        {"$group": {"_id": {"t": "$documento_tipo", "i": "$documento_id"}, "fecha": {"$min": "$fecha"},
                    "numero": {"$first": "$referencia"}, "valor": {"$sum": "$debito"}, "lineas": {"$sum": 1}}},
        {"$sort": {"fecha": -1, "numero": -1}},
        {"$limit": 1000},
    ]):
        nombre, ruta = NOMBRES_DOCUMENTO.get(g["_id"]["t"], (g["_id"]["t"], None))
        filas.append({"documento_tipo": g["_id"]["t"], "documento_id": g["_id"]["i"], "tipo_nombre": nombre, "ruta": ruta,
                      "numero": g["numero"], "fecha": g["fecha"], "valor": round(g["valor"], 2), "lineas": g["lineas"],
                      "estado": "contabilizado"})
    if tipo in (None, "", "comprobante"):
        # Comprobantes que aún no están en el libro (borrador, por aprobar, rechazados) o anulados.
        filtro = {"empresa_id": empresa_id, "estado": {"$ne": "contabilizado"}}
        if "fecha" in match:
            filtro["fecha"] = match["fecha"]
        if q:
            filtro["numero"] = match["referencia"]
        async for c in db.comprobantes_contables.find(filtro):
            filas.append({"documento_tipo": "comprobante", "documento_id": str(c["_id"]), "tipo_nombre": NOMBRES_DOCUMENTO["comprobante"][0],
                          "ruta": NOMBRES_DOCUMENTO["comprobante"][1], "numero": c.get("numero"), "fecha": c.get("fecha"),
                          "valor": round(sum(float(l.get("debito", 0)) for l in c.get("lineas", [])), 2),
                          "lineas": len(c.get("lineas", [])), "estado": c.get("estado")})
        filas.sort(key=lambda f: (f["fecha"] or "", f["numero"] or ""), reverse=True)
    return filas


@router.get("/documentos/{documento_tipo}/{documento_id}/asientos")
async def asientos_de_documento(
    documento_tipo: str,
    documento_id: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    """El comprobante contable de un documento: sus líneas, terceros, quién lo elaboró y quién lo aprobó."""
    db = get_db()
    lineas = [d async for d in db.asientos_contables.find(
        {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id}).sort("_id", 1)]
    cuentas = {str(c["_id"]): c async for c in db.plan_cuentas.find({"empresa_id": empresa_id})}
    ids_t = [oid(l["tercero_id"]) for l in lineas if l.get("tercero_id")]
    terceros = {str(t["_id"]): t async for t in db.terceros.find({"_id": {"$in": ids_t}})} if ids_t else {}
    creado = await db.auditoria.find_one(
        {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id, "accion": "creado"},
        sort=[("fecha_hora", 1)])
    aprobado = await db.auditoria.find_one(
        {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id, "accion": "aprobado"},
        sort=[("fecha_hora", -1)])
    nombres = await _nombres(empresa_id, {(creado or {}).get("usuario_id"), (aprobado or {}).get("usuario_id")})
    if not lineas and not creado:
        raise HTTPException(404, "El documento no tiene asientos")
    nombre, ruta = NOMBRES_DOCUMENTO.get(documento_tipo, (documento_tipo, None))
    return {
        "documento_tipo": documento_tipo, "tipo_nombre": nombre, "ruta": ruta,
        "numero": lineas[0]["referencia"] if lineas else (creado or {}).get("numero"),
        "fecha": lineas[0]["fecha"] if lineas else None,
        "elaboro": nombres.get((creado or {}).get("usuario_id", ""), ""),
        "aprobo": nombres.get((aprobado or {}).get("usuario_id", ""), ""),
        "lineas": [{"cuenta_codigo": l.get("cuenta_codigo"), "cuenta_nombre": cuentas.get(l["cuenta_puc_id"], {}).get("nombre", ""),
                    "tercero": terceros.get(l.get("tercero_id") or "", {}).get("nombre", ""),
                    "tercero_documento": terceros.get(l.get("tercero_id") or "", {}).get("numero_documento", ""),
                    "descripcion": l.get("descripcion") or "", "debito": l.get("debito", 0), "credito": l.get("credito", 0)}
                   for l in lineas],
        "total_debito": round(sum(l.get("debito", 0) for l in lineas), 2),
        "total_credito": round(sum(l.get("credito", 0) for l in lineas), 2),
    }


# ---------------------------------------------------------------------------
# Comprobante de cierre: saldos de las cuentas de resultado y asiento sugerido
# ---------------------------------------------------------------------------

@router.get("/cierre-sugerido")
async def cierre_sugerido(
    desde: str = Query(...),
    hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    """Saldo de cada cuenta de resultado (clases 4, 5, 6 y 7) y el asiento que las lleva a cero contra la utilidad o pérdida."""
    db = get_db()
    saldos = defaultdict(lambda: {"debito": 0.0, "credito": 0.0})
    async for g in await db.asientos_contables.aggregate([
        {"$match": {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}, "cuenta_codigo": {"$regex": "^[4567]"}}},
        {"$group": {"_id": "$cuenta_puc_id", "debito": {"$sum": "$debito"}, "credito": {"$sum": "$credito"}}},
    ]):
        saldos[g["_id"]] = {"debito": g["debito"], "credito": g["credito"]}
    cuentas = {str(c["_id"]): c async for c in db.plan_cuentas.find({"empresa_id": empresa_id})}
    filas, lineas = [], []
    resultado = 0.0
    for cid, v in sorted(saldos.items(), key=lambda kv: cuentas.get(kv[0], {}).get("codigo", "")):
        neto = round(v["credito"] - v["debito"], 2)   # + ingreso, − costo o gasto
        if abs(neto) < 0.005:
            continue
        c = cuentas.get(cid, {})
        resultado += neto
        filas.append({"cuenta_puc_id": cid, "codigo": c.get("codigo", ""), "nombre": c.get("nombre", ""), "saldo": neto,
                      "naturaleza": "crédito" if neto > 0 else "débito"})
        # Se cierra la cuenta llevándola a cero: lo que tenía saldo crédito se debita y al revés.
        lineas.append({"cuenta_puc_id": cid, "descripcion": "Cierre de cuenta de resultado",
                       "debito": neto if neto > 0 else 0, "credito": -neto if neto < 0 else 0})
    resultado = round(resultado, 2)
    contrapartida = None
    if abs(resultado) >= 0.005:
        codigo = "3605" if resultado > 0 else "3610"
        cuenta = next((c for c in cuentas.values() if c.get("codigo") == codigo), None)
        if cuenta:
            contrapartida = {"cuenta_puc_id": str(cuenta["_id"]), "codigo": codigo, "nombre": cuenta["nombre"]}
            lineas.append({"cuenta_puc_id": str(cuenta["_id"]),
                           "descripcion": "Utilidad del ejercicio" if resultado > 0 else "Pérdida del ejercicio",
                           "debito": -resultado if resultado < 0 else 0, "credito": resultado if resultado > 0 else 0})
    return {"desde": desde, "hasta": hasta, "saldos": filas, "resultado": resultado,
            "tipo_resultado": "utilidad" if resultado > 0 else ("pérdida" if resultado < 0 else "sin movimiento"),
            "contrapartida": contrapartida, "lineas": lineas}
