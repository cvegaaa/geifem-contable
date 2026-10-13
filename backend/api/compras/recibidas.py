"""Facturas electrónicas recibidas de proveedores: lectura del XML (UBL 2.1), eventos RADIAN y contabilización.

- Se carga el XML (o el AttachedDocument) que envía el proveedor; se guarda con su CUFE (único por empresa).
- Los eventos RADIAN (acuse, reclamo, recibo del bien, aceptación expresa) se registran con su secuencia
  válida y quedan «pendientes de transmisión»: el envío a la DIAN lo hará el proveedor tecnológico.
- Al contabilizar se crea la factura de proveedor (con sus retenciones, IVA y asiento) ligada al CUFE.
"""
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from core.auth.dependencies import get_empresa_activa, require_permiso
from core.dian import ubl
from core.documentos import (
    NO_ANULADO,
    ahora,
    auditar,
    en_transaccion,
    formatear_numero,
    oid,
    serializar,
    siguiente_consecutivo,
)
from db import get_db

router = APIRouter()

RECIBIDA = "factura_recibida"
EVENTOS = {
    "030": "Acuse de recibo de la factura electrónica",
    "031": "Reclamo de la factura electrónica",
    "032": "Recibo del bien o prestación del servicio",
    "033": "Aceptación expresa",
}
MOTIVOS_RECLAMO = {
    "01": "Documento con inconsistencias",
    "02": "Mercancía no entregada totalmente",
    "03": "Mercancía no entregada parcialmente",
    "04": "Servicio no prestado",
}


def _nit_empresa(empresa: dict | None) -> str:
    return re.sub(r"\D", "", (empresa or {}).get("nit", "") or "")


def _estado_radian(eventos: list[dict]) -> str:
    codigos = {e["codigo"] for e in eventos}
    if "033" in codigos:
        return "aceptada"
    if "031" in codigos:
        return "reclamada"
    if "032" in codigos:
        return "bien recibido"
    if "030" in codigos:
        return "acusada"
    return "pendiente"


async def _leer(empresa_id: str, contenido: bytes) -> tuple[dict, list[str]]:
    """Lee el XML y revisa que sea para esta empresa y que no esté repetida."""
    try:
        datos = ubl.leer_factura(contenido)
    except ubl.XmlInvalido as e:
        raise HTTPException(422, str(e))
    db = get_db()
    empresa = await db.empresas.find_one({"_id": oid(empresa_id)})
    if datos["adquirente"].get("nit") and datos["adquirente"]["nit"] != _nit_empresa(empresa):
        raise HTTPException(409, f"La factura está a nombre del NIT {datos['adquirente']['nit']}, no de esta empresa")
    if await db.facturas_recibidas.find_one({"empresa_id": empresa_id, "cufe": datos["cufe"]}):
        raise HTTPException(409, "Esta factura (CUFE) ya fue cargada")
    avisos = []
    if datos["tipo"] not in ubl.TIPOS_FACTURA:
        avisos.append(f"Tipo de documento {datos['tipo']}: no es una factura de venta; revísala antes de contabilizar.")
    if datos["moneda"] != "COP":
        avisos.append(f"La factura está en {datos['moneda']}: se contabilizaría tal cual, sin conversión.")
    calc_sub = sum(i["subtotal"] for i in datos["items"])
    if datos["subtotal_xml"] is not None and abs(calc_sub - datos["subtotal_xml"] - sum(i["inc"] for i in datos["items"])) > 1:
        avisos.append("La suma de las líneas no coincide con el total del XML; verifica los valores.")
    prov = datos["proveedor"]
    existente = await db.terceros.find_one({"empresa_id": empresa_id, "numero_documento": prov.get("nit")}) if prov.get("nit") else None
    datos["proveedor_existente_id"] = str(existente["_id"]) if existente else None
    if not existente:
        avisos.append("El proveedor no existe: se creará al contabilizar.")
    return datos, avisos


@router.get("/facturas-recibidas")
async def listar_recibidas(
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    cursor = get_db().facturas_recibidas.find({"empresa_id": empresa_id}, {"xml": 0}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@router.post("/facturas-recibidas", status_code=201)
async def cargar_recibida(
    archivo: UploadFile = File(...),
    simular: bool = Query(False, description="Solo lee y valida el XML, sin guardar"),
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    contenido = await archivo.read(ubl.MAX_BYTES + 1)
    datos, avisos = await _leer(empresa_id, contenido)
    if simular:
        return {"guardada": False, "avisos": avisos, "factura": datos}
    db = get_db()

    async def _tx(s):
        consecutivo = await siguiente_consecutivo(empresa_id, "factura_recibida", s)
        doc = {**datos, "empresa_id": empresa_id, "prefijo": "FR", "consecutivo": consecutivo,
               "numero": formatear_numero("FR", consecutivo), "proveedor_nombre": datos["proveedor"].get("nombre", ""),
               "proveedor_nit": datos["proveedor"].get("nit", ""), "subtotal": round(sum(i["subtotal"] for i in datos["items"]), 2),
               "iva_total": round(sum(i["iva"] for i in datos["items"]), 2),
               "total": datos["total_xml"], "xml": contenido.decode("utf-8", errors="replace"),
               "eventos": [], "estado_radian": "pendiente", "contabilizada": False, "factura_proveedor_id": None,
               "estado": "recibida", "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.facturas_recibidas.insert_one(doc, session=s)
        await auditar(empresa_id, RECIBIDA, str(res.inserted_id), doc["numero"], usuario["id"], "creado", s,
                      {"cufe": datos["cufe"]})
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    doc = await db.facturas_recibidas.find_one({"_id": nuevo}, {"xml": 0})
    return {"guardada": True, "avisos": avisos, "factura": serializar(doc)}


@router.get("/facturas-recibidas/{rid}")
async def obtener_recibida(
    rid: str,
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("compras", "leer")),
):
    doc = await get_db().facturas_recibidas.find_one({"_id": oid(rid), "empresa_id": empresa_id}, {"xml": 0})
    if not doc:
        raise HTTPException(404, "Factura recibida no encontrada")
    return serializar(doc)


# ---------------------------------------------------------------------------
# Eventos RADIAN
# ---------------------------------------------------------------------------

class EventoRadian(BaseModel):
    codigo: Literal["030", "031", "032", "033"]
    fecha: str | None = None
    motivo: Literal["01", "02", "03", "04"] | None = None
    observaciones: str | None = None


def _validar_secuencia(codigo: str, previos: set[str], motivo: str | None) -> None:
    if codigo in previos:
        raise HTTPException(409, f"El evento {codigo} ya está registrado")
    if codigo != "030" and "030" not in previos:
        raise HTTPException(409, "Primero registra el acuse de recibo (030)")
    if codigo == "033":
        if "032" not in previos:
            raise HTTPException(409, "La aceptación expresa requiere el recibo del bien o servicio (032)")
        if "031" in previos:
            raise HTTPException(409, "No se puede aceptar una factura con reclamo")
    if codigo == "031":
        if "033" in previos:
            raise HTTPException(409, "No se puede reclamar una factura ya aceptada")
        if not motivo:
            raise HTTPException(422, "El reclamo necesita el motivo (01 a 04)")


@router.post("/facturas-recibidas/{rid}/eventos", status_code=201)
async def registrar_evento(
    rid: str,
    payload: EventoRadian,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "editar")),
):
    db = get_db()

    async def _tx(s):
        doc = await db.facturas_recibidas.find_one({"_id": oid(rid), "empresa_id": empresa_id}, session=s)
        if not doc:
            raise HTTPException(404, "Factura recibida no encontrada")
        if doc.get("contabilizada") and payload.codigo == "031":
            raise HTTPException(409, "La factura ya está contabilizada: anula primero la factura de proveedor")
        eventos = doc.get("eventos", [])
        _validar_secuencia(payload.codigo, {e["codigo"] for e in eventos}, payload.motivo)
        evento = {"codigo": payload.codigo, "nombre": EVENTOS[payload.codigo], "fecha": payload.fecha or date.today().isoformat(),
                  "motivo": payload.motivo, "motivo_nombre": MOTIVOS_RECLAMO.get(payload.motivo or ""),
                  "observaciones": payload.observaciones, "registrado_por": usuario["id"], "registrado_en": ahora(),
                  "transmision": "pendiente"}
        eventos.append(evento)
        estado = _estado_radian(eventos)
        await db.facturas_recibidas.update_one(
            {"_id": doc["_id"]}, {"$set": {"eventos": eventos, "estado_radian": estado}}, session=s)
        await auditar(empresa_id, RECIBIDA, rid, doc["numero"], usuario["id"], f"evento {payload.codigo}", s)

    await en_transaccion(_tx)
    return serializar(await db.facturas_recibidas.find_one({"_id": oid(rid)}, {"xml": 0}))


# ---------------------------------------------------------------------------
# Contabilizar: crea la factura de proveedor
# ---------------------------------------------------------------------------

class Contabilizar(BaseModel):
    afecta_inventario: bool = False
    cuenta_gasto: str | None = None
    aplicar_reteiva: bool = True
    concepto_reteica_id: str | None = None
    # índice de la línea del XML -> producto del catálogo
    productos: dict[int, str] = Field(default_factory=dict)
    # índice de la línea -> concepto de ReteFuente
    conceptos_retefuente: dict[int, str] = Field(default_factory=dict)
    crear_proveedor: bool = True


@router.post("/facturas-recibidas/{rid}/contabilizar", status_code=201)
async def contabilizar_recibida(
    rid: str,
    payload: Contabilizar,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("compras", "crear")),
):
    from api.compras import FacturaProveedorCrear, ItemCompra, crear_factura_proveedor_doc

    db = get_db()

    async def _tx(s):
        doc = await db.facturas_recibidas.find_one({"_id": oid(rid), "empresa_id": empresa_id}, session=s)
        if not doc:
            raise HTTPException(404, "Factura recibida no encontrada")
        if doc.get("contabilizada"):
            raise HTTPException(409, "La factura ya está contabilizada")
        if doc.get("estado_radian") == "reclamada":
            raise HTTPException(409, "La factura tiene un reclamo: no se contabiliza")
        prov = doc["proveedor"]
        tercero = await db.terceros.find_one({"empresa_id": empresa_id, "numero_documento": prov.get("nit")}, session=s)
        if not tercero:
            if not payload.crear_proveedor:
                raise HTTPException(409, "El proveedor no existe en terceros")
            nuevo = {"empresa_id": empresa_id, "nombre": prov.get("nombre") or prov.get("nit"), "tipo": "proveedor",
                     "tipo_documento": "NIT", "numero_documento": prov.get("nit"), "dv": prov.get("dv"),
                     "email": prov.get("email"), "regimen": "ORDINARIO", "responsable_iva": True, "activo": True,
                     "fecha_creacion": ahora()}
            res = await db.terceros.insert_one(nuevo, session=s)
            tercero_id = str(res.inserted_id)
        else:
            tercero_id = str(tercero["_id"])
        items = [ItemCompra(producto_id=payload.productos.get(i) or None, descripcion=it["descripcion"], cantidad=it["cantidad"],
                            costo_unitario=it["costo_unitario"], tarifa_iva=it["tarifa_iva"],
                            concepto_retefuente_id=payload.conceptos_retefuente.get(i) or None)
                 for i, it in enumerate(doc["items"])]
        cuerpo = FacturaProveedorCrear(
            proveedor_id=tercero_id, numero_factura=doc["numero_factura"], fecha=doc["fecha"],
            fecha_vencimiento=doc.get("fecha_vencimiento"), afecta_inventario=payload.afecta_inventario,
            cuenta_gasto=payload.cuenta_gasto, concepto_reteica_id=payload.concepto_reteica_id,
            aplicar_reteiva=payload.aplicar_reteiva, observaciones=f"CUFE {doc['cufe']}", items=items)
        fid = await crear_factura_proveedor_doc(
            empresa_id, cuerpo, usuario["id"], s,
            {"cufe": doc["cufe"], "origen": "xml_dian", "factura_recibida_id": rid})
        await db.facturas_recibidas.update_one(
            {"_id": doc["_id"]}, {"$set": {"contabilizada": True, "factura_proveedor_id": str(fid)}}, session=s)
        await auditar(empresa_id, RECIBIDA, rid, doc["numero"], usuario["id"], "contabilizada", s)
        return fid

    fid = await en_transaccion(_tx)
    factura = await db.facturas_proveedor.find_one({"_id": fid})
    return serializar(factura)
