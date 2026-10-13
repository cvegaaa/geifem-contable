"""Motor común de documentos: numeración, asientos, auditoría y transacciones.

Reglas de negocio compartidas por todos los documentos (comprobantes,
facturas, compras, tesorería, inventario):

- La numeración es automática, consecutiva y atómica por empresa y tipo
  (colección `contadores`).
- Los efectos de un documento (asientos contables, movimientos de inventario,
  saldos) quedan marcados con `documento_tipo` + `documento_id`; editar un
  documento revierte sus efectos y los vuelve a aplicar, anularlo los revierte.
- Un documento numerado no se elimina: se **anula**, conservando su número
  para que la secuencia no tenga huecos (requisito contable).
- Todo cambio queda en la colección `auditoria`.
"""
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import TypeVar

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession

from db import get_client, get_db
from core.dinero import centavos, redondear

T = TypeVar("T")

# Aprobador de la solicitud que se está ejecutando (None en el flujo normal); lo usa la auditoría.
APROBADOR: ContextVar[str | None] = ContextVar("aprobador", default=None)

# Filtro para excluir documentos anulados en consultas y reportes.
NO_ANULADO = {"estado": {"$ne": "anulado"}}


def oid(valor: str | None, campo: str = "id") -> ObjectId:
    try:
        return ObjectId(valor)
    except Exception:
        raise HTTPException(400, f"{campo} inválido")


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def serializar(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def en_transaccion(fn: Callable[[AsyncClientSession], Awaitable[T]]) -> T:
    """Ejecuta `fn(sesion)` en una transacción (se reintenta ante conflictos transitorios)."""
    async with get_client().start_session() as s:
        return await s.with_transaction(fn)


async def siguiente_consecutivo(empresa_id: str, clave: str, s: AsyncClientSession) -> int:
    doc = await get_db().contadores.find_one_and_update(
        {"empresa_id": empresa_id, "clave": clave},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        session=s,
    )
    return int(doc["valor"])


def formatear_numero(prefijo: str, consecutivo: int) -> str:
    return f"{prefijo}-{consecutivo}"


async def cargar_editable(
    coleccion: str, empresa_id: str, doc_id: str, s: AsyncClientSession | None = None
) -> dict:
    """Trae un documento de la empresa y verifica que no esté anulado."""
    doc = await get_db()[coleccion].find_one(
        {"_id": oid(doc_id), "empresa_id": empresa_id}, session=s
    )
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    if doc.get("estado") == "anulado":
        raise HTTPException(409, "El documento está anulado")
    return doc


def campos_conservados(existente: dict) -> dict:
    """Campos que una edición nunca cambia (identidad y numeración)."""
    claves = ("empresa_id", "prefijo", "consecutivo", "numero", "creado_por", "fecha_creacion")
    return {k: existente[k] for k in claves if k in existente}


def marca_anulacion(usuario_id: str, motivo: str | None) -> dict:
    return {
        "estado": "anulado",
        "anulado_por": usuario_id,
        "fecha_anulacion": ahora(),
        "motivo_anulacion": motivo or "",
    }


# ---------------------------------------------------------------------------
# Asientos contables (libro)
# ---------------------------------------------------------------------------

class Linea:
    """Línea de asiento. Usa `codigo` (PUC) o `cuenta_id` (id del plan de la empresa)."""

    __slots__ = ("codigo", "cuenta_id", "debito", "credito", "tercero_id", "descripcion")

    def __init__(self, *, codigo: str | None = None, cuenta_id: str | None = None,
                 debito: float = 0.0, credito: float = 0.0,
                 tercero_id: str | None = None, descripcion: str | None = None):
        self.codigo = codigo
        self.cuenta_id = cuenta_id
        self.debito = redondear(float(debito or 0), 2)
        self.credito = redondear(float(credito or 0), 2)
        self.tercero_id = tercero_id
        self.descripcion = descripcion


async def fecha_cierre(empresa_id: str, s: AsyncClientSession | None = None) -> str | None:
    """Último día cerrado de la contabilidad de la empresa (AAAA-MM-DD), si lo hay."""
    emp = await get_db().empresas.find_one({"_id": oid(empresa_id)}, {"fecha_cierre": 1}, session=s)
    return (emp or {}).get("fecha_cierre")


async def exigir_periodo_abierto(empresa_id: str, fecha: str, s: AsyncClientSession | None = None) -> None:
    cierre = await fecha_cierre(empresa_id, s)
    if cierre and str(fecha) <= cierre:
        raise HTTPException(
            409,
            f"El periodo está cerrado hasta el {cierre}: no se pueden registrar, modificar ni anular "
            f"documentos con fecha {fecha}. Pide a un administrador que lo reabra.",
        )


async def registrar_asientos(
    empresa_id: str, documento_tipo: str, documento_id: str, numero: str, fecha: str,
    lineas: list[Linea], s: AsyncClientSession,
) -> None:
    """Valida periodo, cuentas y cuadre, y graba las líneas del documento en el libro."""
    await exigir_periodo_abierto(empresa_id, fecha, s)
    lineas = [l for l in lineas if l.debito or l.credito]
    if not lineas:
        return
    # El cuadre se compara en centavos enteros: sin error de punto flotante.
    total_deb = sum(centavos(l.debito) for l in lineas)
    total_cre = sum(centavos(l.credito) for l in lineas)
    if total_deb != total_cre:
        raise HTTPException(422, f"Asiento descuadrado: débitos {total_deb / 100:,.2f} ≠ créditos {total_cre / 100:,.2f}")

    db = get_db()
    momento = ahora()
    docs = []
    for l in lineas:
        if l.cuenta_id:
            cuenta = await db.plan_cuentas.find_one(
                {"_id": oid(l.cuenta_id, "cuenta"), "empresa_id": empresa_id}, session=s
            )
        else:
            cuenta = await db.plan_cuentas.find_one(
                {"empresa_id": empresa_id, "codigo": l.codigo}, session=s
            )
        if not cuenta or cuenta.get("activo") is False:
            ref = l.codigo or l.cuenta_id
            raise HTTPException(422, f"La cuenta {ref} no existe o está inactiva en el plan de cuentas")
        if cuenta.get("acepta_movimientos") is False:
            raise HTTPException(
                422, f"La cuenta {cuenta['codigo']} {cuenta['nombre']} es de agrupación y no recibe movimientos"
            )
        docs.append({
            "empresa_id": empresa_id,
            "fecha": fecha,
            "cuenta_puc_id": str(cuenta["_id"]),
            "cuenta_codigo": cuenta["codigo"],
            "tercero_id": l.tercero_id,
            "debito": l.debito,
            "credito": l.credito,
            "descripcion": l.descripcion,
            "referencia": numero,
            "documento_tipo": documento_tipo,
            "documento_id": documento_id,
            "fecha_creacion": momento,
        })
    await db.asientos_contables.insert_many(docs, session=s)


async def borrar_asientos(
    empresa_id: str, documento_tipo: str, documento_id: str, s: AsyncClientSession
) -> None:
    # Editar o anular un documento reescribe su asiento: no se permite si cae en un periodo cerrado.
    cierre = await fecha_cierre(empresa_id, s)
    if cierre:
        cerrado = await get_db().asientos_contables.find_one(
            {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id,
             "fecha": {"$lte": cierre}}, session=s)
        if cerrado:
            raise HTTPException(
                409,
                f"El documento pertenece a un periodo cerrado (hasta el {cierre}): no se puede modificar ni anular. "
                "Corrígelo con un comprobante de ajuste en el periodo abierto o pide reabrir el periodo.",
            )
    await get_db().asientos_contables.delete_many(
        {"empresa_id": empresa_id, "documento_tipo": documento_tipo, "documento_id": documento_id},
        session=s,
    )


# ---------------------------------------------------------------------------
# Auditoría
# ---------------------------------------------------------------------------

async def auditar(
    empresa_id: str, documento_tipo: str, documento_id: str, numero: str | None,
    usuario_id: str, accion: str, s: AsyncClientSession | None = None,
    detalle: dict | None = None,
) -> None:
    momento = ahora()
    eventos = [{
        "empresa_id": empresa_id,
        "documento_tipo": documento_tipo,
        "documento_id": documento_id,
        "numero": numero,
        "usuario_id": usuario_id,
        "accion": accion,  # creado | editado | anulado | aprobado ...
        "fecha_hora": momento,
        "detalle": detalle or {},
    }]
    aprobador = APROBADOR.get()
    if aprobador and accion in ("creado", "editado", "anulado"):
        # El documento lo registró quien lo solicitó, pero lo autorizó otro usuario: queda constancia.
        eventos.append({**eventos[0], "usuario_id": aprobador, "accion": "aprobado", "detalle": {"solicitud": accion}})
    await get_db().auditoria.insert_many(eventos, session=s)


# Nombre legible y pantalla de cada tipo de documento que escribe en el libro o en la auditoría.
NOMBRES_DOCUMENTO: dict[str, tuple[str, str | None]] = {
    "comprobante": ("Comprobante contable", "/contabilidad/consulta-comprobantes"),
    "factura": ("Factura de venta", "/facturacion/factura-venta"),
    "pos": ("Documento equivalente POS", "/facturacion/documento-equivalente-pos"),
    "nota": ("Nota crédito/débito", "/facturacion/notas-credito-debito"),
    "orden_compra": ("Orden de compra", "/compras/ordenes-compra"),
    "recepcion": ("Entrada de mercancía", "/compras/recepcion-mercancia"),
    "factura_proveedor": ("Factura de proveedor", "/compras/facturas-proveedor"),
    "factura_recibida": ("Factura electrónica recibida", "/compras/facturas-recibidas"),
    "devolucion_proveedor": ("Devolución a proveedor", "/compras/devoluciones-proveedor"),
    "movimiento_tesoreria": ("Movimiento de caja/banco", "/tesoreria/caja"),
    "pago": ("Recibo de caja / comprobante de egreso", "/tesoreria/cxc-cxp"),
    "anticipo": ("Anticipo", "/tesoreria/anticipos"),
    "aplicacion_anticipo": ("Aplicación de anticipo", "/tesoreria/anticipos"),
    "transferencia": ("Transferencia entre cuentas", "/tesoreria/transferencias"),
    "cartera_inicial": ("Saldo inicial de cartera", "/tesoreria/cxc-cxp"),
    "ajuste_inventario": ("Ajuste de inventario", "/inventario/ajustes-inventario"),
    "ajuste_costo": ("Ajuste de costo de venta", None),
    "saldo_inicial": ("Saldo inicial de caja o banco", "/tesoreria/caja"),
    "nomina_periodo": ("Liquidación de nómina", "/nomina/periodos"),
    "pago_nomina": ("Pago de nómina", "/nomina/periodos"),
    "pago_obligacion": ("Pago de prestaciones / aportes", "/nomina/prestaciones"),
    "nomina_liquidacion_final": ("Liquidación de contrato", "/nomina/liquidacion-contrato"),
    "cuenta_caja": ("Caja", "/tesoreria/caja"),
    "cuenta_banco": ("Cuenta bancaria", "/tesoreria/bancos"),
    "cierre_periodo": ("Cierre de periodo", "/contabilidad/cierre-periodos"),
}
