"""Cartera (cuentas por cobrar y por pagar): documentos de origen.

Una cuenta por cobrar o por pagar puede venir de una factura (de venta o de proveedor) o de un **saldo inicial
de cartera**: la línea de clientes o proveedores de un comprobante de apertura, detallada por tercero y documento.
Ambos viven en colecciones distintas pero se tratan igual (pagos, anticipos, antigüedad, estado de cuenta, reportes).
"""
from collections.abc import AsyncIterator

from fastapi import HTTPException
from pymongo.asynchronous.client_session import AsyncClientSession

from core import parametros
from core.documentos import NO_ANULADO, ahora, oid
from db import get_db

INICIAL = "cartera_inicial"


def principal(tipo: str) -> str:
    return "facturas" if tipo in ("cxc", "cliente") else "facturas_proveedor"


def es_cxc(tipo: str) -> bool:
    return tipo in ("cxc", "cliente")


async def buscar(db, tipo: str, doc_id: str, empresa_id: str, s: AsyncClientSession | None = None,
                 extra: dict | None = None) -> tuple[str | None, dict | None]:
    """(colección, documento) de una cuenta por cobrar/pagar, sea factura o saldo inicial."""
    _id = oid(doc_id, "documento_id")
    t = "cxc" if es_cxc(tipo) else "cxp"
    doc = await db[principal(tipo)].find_one({"_id": _id, "empresa_id": empresa_id, **(extra or {})}, session=s)
    if doc:
        return principal(tipo), doc
    doc = await db[INICIAL].find_one({"_id": _id, "empresa_id": empresa_id, "tipo": t, **(extra or {})}, session=s)
    return (INICIAL, doc) if doc else (None, None)


async def iterar(db, empresa_id: str, tipo: str, filtro: dict | None = None) -> AsyncIterator[dict]:
    """Facturas no anuladas y saldos iniciales del tipo, por fecha."""
    t = "cxc" if es_cxc(tipo) else "cxp"
    async for f in db[principal(tipo)].find({"empresa_id": empresa_id, **NO_ANULADO, **(filtro or {})}).sort("fecha", 1):
        yield f
    async for f in db[INICIAL].find({"empresa_id": empresa_id, "tipo": t, **(filtro or {})}).sort("fecha", 1):
        yield f


def _lineas_cartera(doc: dict, params: dict[str, str]) -> list[dict]:
    """Líneas de la apertura que son cartera: débito en clientes (CxC) o crédito en proveedores (CxP)."""
    salida = []
    for i, l in enumerate(doc.get("lineas", [])):
        codigo = l.get("_codigo")
        if codigo == params["clientes"] and l.get("debito"):
            salida.append({"tipo": "cxc", "linea": l, "indice": i})
        elif codigo == params["proveedores"] and l.get("credito"):
            salida.append({"tipo": "cxp", "linea": l, "indice": i})
    return salida


async def sincronizar_apertura(empresa_id: str, comprobante_id: str, doc: dict, s: AsyncClientSession) -> None:
    """Deja en `cartera_inicial` los documentos que detalla un comprobante de apertura contabilizado.

    Se llama al crear, editar, aprobar o anular el comprobante: primero retira lo anterior (si nada se ha
    cobrado ni pagado) y luego, si sigue contabilizado, crea un documento por cada línea de clientes o proveedores.
    """
    db = get_db()
    previos = [d async for d in db[INICIAL].find({"empresa_id": empresa_id, "comprobante_id": comprobante_id}, session=s)]
    for p in previos:
        if round(float(p["saldo_pendiente"]), 2) != round(float(p["valor"]), 2):
            raise HTTPException(409, f"El saldo inicial de cartera {p['numero_documento']} ya tiene pagos, anticipos o notas aplicados: "
                                     "anúlalos antes de modificar la apertura")
    if previos:
        await db[INICIAL].delete_many({"empresa_id": empresa_id, "comprobante_id": comprobante_id}, session=s)
    if doc.get("tipo") != "apertura" or doc.get("estado") != "contabilizado":
        return

    params = await parametros.obtener(empresa_id, s)
    cuentas = {str(c["_id"]): c async for c in db.plan_cuentas.find({"empresa_id": empresa_id}, session=s)}
    lineas = [{**l, "_codigo": cuentas.get(l["cuenta_puc_id"], {}).get("codigo")} for l in doc.get("lineas", [])]
    nuevos = []
    for item in _lineas_cartera({"lineas": lineas}, params):
        l = item["linea"]
        tercero_id = l.get("tercero_id") or doc.get("tercero_id")
        numero_doc = (l.get("documento_numero") or "").strip()
        if not tercero_id or not numero_doc:
            raise HTTPException(
                422, "Las líneas de clientes y proveedores en una apertura deben indicar el tercero y el número del documento "
                     "para que queden como cuentas por cobrar o por pagar")
        tercero = await db.terceros.find_one({"_id": oid(tercero_id), "empresa_id": empresa_id}, session=s)
        if not tercero:
            raise HTTPException(404, "Tercero no encontrado")
        valor = round(float(l["debito"] if item["tipo"] == "cxc" else l["credito"]), 2)
        fecha = l.get("fecha_documento") or doc["fecha"]
        base = {"empresa_id": empresa_id, "tipo": item["tipo"], "comprobante_id": comprobante_id,
                "comprobante_numero": doc["numero"], "numero_documento": numero_doc, "fecha": fecha,
                "fecha_vencimiento": l.get("fecha_vencimiento") or fecha, "valor": valor, "saldo_pendiente": valor,
                "estado": "registrada", "saldo_inicial": True, "fecha_creacion": ahora()}
        if item["tipo"] == "cxc":
            base.update({"numero": numero_doc, "cliente_id": tercero_id, "cliente_nombre": tercero.get("nombre", ""),
                         "total": valor, "cuenta_cxc": params["clientes"]})
        else:
            base.update({"numero_factura": numero_doc, "proveedor_id": tercero_id, "proveedor_nombre": tercero.get("nombre", ""),
                         "total_a_pagar": valor, "cuenta_cxp": params["proveedores"]})
        nuevos.append(base)
    if nuevos:
        await db[INICIAL].insert_many(nuevos, session=s)
