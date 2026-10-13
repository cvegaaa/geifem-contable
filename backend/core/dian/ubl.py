"""Lectura de facturas electrónicas colombianas (UBL 2.1 de la DIAN).

Acepta la factura (`Invoice`) y el contenedor `AttachedDocument` que reciben los adquirentes por correo
(la factura va dentro del nodo `Description`). Solo extrae los datos necesarios para contabilizar una compra:
no valida la firma electrónica ni consulta a la DIAN.
"""
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

MAX_BYTES = 3 * 1024 * 1024
TIPOS_FACTURA = {"01": "Factura electrónica de venta", "02": "Factura de exportación", "03": "Factura por contingencia",
                 "04": "Factura por contingencia DIAN"}


class XmlInvalido(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _hijos(nodo, nombre):
    return [h for h in nodo if _local(h.tag) == nombre]


def _hijo(nodo, nombre):
    for h in nodo:
        if _local(h.tag) == nombre:
            return h
    return None


def _ruta(nodo, *nombres):
    for n in nombres:
        nodo = _hijo(nodo, n) if nodo is not None else None
    return nodo


def _texto(nodo, *nombres) -> str | None:
    n = _ruta(nodo, *nombres) if nombres else nodo
    return (n.text or "").strip() if n is not None and n.text else None


def _num(valor: str | None, defecto: float = 0.0) -> float:
    try:
        return float(Decimal((valor or "").replace(",", "")))
    except (InvalidOperation, AttributeError):
        return defecto


def _cargar(contenido: bytes) -> ET.Element:
    if len(contenido) > MAX_BYTES:
        raise XmlInvalido("El archivo es demasiado grande (máximo 3 MB)")
    if re.search(rb"<!(DOCTYPE|ENTITY)", contenido, re.I):
        raise XmlInvalido("El XML contiene definiciones no permitidas")
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as e:
        raise XmlInvalido(f"No es un XML válido: {e}")
    if _local(raiz.tag) == "AttachedDocument":
        for n in raiz.iter():
            if _local(n.tag) == "Description" and n.text and "<Invoice" in n.text:
                return _cargar(n.text.strip().encode("utf-8"))
        raise XmlInvalido("El AttachedDocument no trae la factura dentro")
    if _local(raiz.tag) != "Invoice":
        raise XmlInvalido("El archivo no es una factura electrónica (nodo raíz Invoice)")
    return raiz


def _parte(nodo) -> dict:
    """Datos de un tercero (AccountingSupplierParty / AccountingCustomerParty)."""
    party = _hijo(nodo, "Party") if nodo is not None else None
    if party is None:
        return {}
    legal = _hijo(party, "PartyLegalEntity")
    tax = _hijo(party, "PartyTaxScheme")
    id_nodo = _ruta(legal, "CompanyID") if legal is not None else None
    if id_nodo is None and tax is not None:
        id_nodo = _hijo(tax, "CompanyID")
    nombre = (_texto(legal, "RegistrationName") if legal is not None else None) or \
        (_texto(tax, "RegistrationName") if tax is not None else None) or \
        _texto(_ruta(party, "PartyName"), "Name")
    numero = re.sub(r"\D", "", (id_nodo.text or "")) if id_nodo is not None and id_nodo.text else ""
    correo = _texto(_ruta(party, "Contact"), "ElectronicMail")
    return {"nombre": nombre or "", "nit": numero, "dv": (id_nodo.get("schemeID") if id_nodo is not None else None),
            "tipo_documento": (id_nodo.get("schemeName") if id_nodo is not None else None), "email": correo}


def _iva(linea) -> tuple[float, float]:
    """(porcentaje de IVA, impuesto al consumo) de una línea."""
    pct, inc = 0.0, 0.0
    for tt in _hijos(linea, "TaxTotal"):
        for sub in _hijos(tt, "TaxSubtotal"):
            cat = _hijo(sub, "TaxCategory")
            codigo = _texto(_ruta(cat, "TaxScheme"), "ID") if cat is not None else None
            if codigo == "01":
                pct = max(pct, _num(_texto(cat, "Percent")))
            elif codigo == "04":
                inc += _num(_texto(sub, "TaxAmount"))
    return pct, inc


def leer_factura(contenido: bytes) -> dict:
    raiz = _cargar(contenido)
    cufe = _texto(raiz, "UUID")
    numero = _texto(raiz, "ID")
    if not cufe or not numero:
        raise XmlInvalido("Faltan el CUFE (UUID) o el número de la factura")
    tipo = _texto(raiz, "InvoiceTypeCode") or "01"
    vence = _texto(raiz, "DueDate") or _texto(_ruta(raiz, "PaymentMeans"), "PaymentDueDate")
    proveedor = _parte(_hijo(raiz, "AccountingSupplierParty"))
    adquirente = _parte(_hijo(raiz, "AccountingCustomerParty"))

    items = []
    for ln in _hijos(raiz, "InvoiceLine"):
        cantidad = _num(_texto(ln, "InvoicedQuantity"), 1.0) or 1.0
        neto = _num(_texto(ln, "LineExtensionAmount"))
        pct, inc = _iva(ln)
        item = _hijo(ln, "Item")
        descripcion = (_texto(item, "Description") or _texto(item, "Name") or "Ítem") if item is not None else "Ítem"
        codigo = None
        if item is not None:
            codigo = _texto(_ruta(item, "SellersItemIdentification"), "ID")
        # El impuesto al consumo no es descontable: mayor valor del costo o gasto.
        base = neto + inc
        items.append({"descripcion": descripcion, "codigo": codigo, "cantidad": cantidad,
                      "costo_unitario": round(base / cantidad, 6), "tarifa_iva": pct,
                      "subtotal": round(base, 2), "iva": round(neto * pct / 100, 2), "inc": round(inc, 2)})
    if not items:
        raise XmlInvalido("La factura no tiene líneas")

    total_xml = _hijo(raiz, "LegalMonetaryTotal")
    iva_total = 0.0
    for tt in _hijos(raiz, "TaxTotal"):
        for sub in _hijos(tt, "TaxSubtotal"):
            cat = _hijo(sub, "TaxCategory")
            if cat is not None and _texto(_ruta(cat, "TaxScheme"), "ID") == "01":
                iva_total += _num(_texto(sub, "TaxAmount"))
    return {
        "cufe": cufe, "numero_factura": numero, "tipo": tipo, "tipo_nombre": TIPOS_FACTURA.get(tipo, f"Documento {tipo}"),
        "fecha": _texto(raiz, "IssueDate"), "hora": _texto(raiz, "IssueTime"), "fecha_vencimiento": vence,
        "moneda": _texto(raiz, "DocumentCurrencyCode") or "COP",
        "proveedor": proveedor, "adquirente": adquirente, "items": items,
        "subtotal_xml": _num(_texto(total_xml, "LineExtensionAmount")) if total_xml is not None else None,
        "iva_xml": round(iva_total, 2),
        "total_xml": _num(_texto(total_xml, "PayableAmount")) if total_xml is not None else None,
        "observaciones": _texto(raiz, "Note"),
    }
