"""Contabilidad: comprobantes manuales (ajuste, nota, apertura, cierre) y auditoría.

Un comprobante en estado `contabilizado` escribe sus líneas en el libro
(`asientos_contables`), de donde salen todos los reportes contables. En
`borrador` no afecta el libro.
"""
from typing import Literal

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from core.auth.dependencies import get_empresa_activa, require_permiso
from core.documentos import (
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


class Anulacion(BaseModel):
    motivo: str | None = None


def _validar_cuadre(payload: ComprobanteCrear) -> None:
    deb = sum(centavos(l.debito) for l in payload.lineas)
    cre = sum(centavos(l.credito) for l in payload.lineas)
    if deb != cre:
        raise HTTPException(422, f"Comprobante descuadrado: débitos {deb / 100:,.2f} ≠ créditos {cre / 100:,.2f}")


async def _aplicar(empresa_id: str, doc_id: str, doc: dict, s) -> None:
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

    async def _tx(s):
        prefijo = PREFIJOS[payload.tipo]
        consecutivo = await siguiente_consecutivo(empresa_id, f"comprobante:{payload.tipo}", s)
        doc = {
            **payload.model_dump(),
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
        await auditar(empresa_id, DOC_TIPO, doc_id, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.comprobantes_contables.find_one({"_id": nuevo}))


@router.get("/comprobantes")
async def consultar_comprobantes(
    tipo: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if tipo:
        filtro["tipo"] = tipo
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

    async def _tx(s):
        existente = await cargar_editable("comprobantes_contables", empresa_id, cid, s)
        if payload.tipo != existente["tipo"]:
            raise HTTPException(409, "No se puede cambiar el tipo de un comprobante ya numerado")
        await borrar_asientos(empresa_id, DOC_TIPO, cid, s)
        doc = {
            **payload.model_dump(),
            **campos_conservados(existente),
            "editado_por": usuario["id"],
            "fecha_actualizacion": ahora(),
        }
        await db.comprobantes_contables.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar(empresa_id, cid, doc, s)
        await auditar(empresa_id, DOC_TIPO, cid, doc["numero"], usuario["id"], "editado", s)

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
            {"empresa_id": empresa_id, "estado": "borrador", "fecha": {"$lte": nueva}})
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


@router.get("/auditoria")
async def listar_auditoria(
    documento_id: str | None = Query(None),
    documento_tipo: str | None = Query(None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("contabilidad", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if documento_id:
        filtro["documento_id"] = documento_id
    if documento_tipo:
        filtro["documento_tipo"] = documento_tipo
    cursor = get_db().auditoria.find(filtro).sort("fecha_hora", -1).limit(500)
    return [serializar(d) async for d in cursor]
