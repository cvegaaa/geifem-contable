"""PDF de los documentos de venta (factura, documento POS y notas crédito/débito)."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.letras import valor_en_letras

AZUL = colors.HexColor("#14315E")
GRIS = colors.HexColor("#64748B")


def _cop(v) -> str:
    return "$" + f"{float(v or 0):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _titulo(tipo: str, doc: dict) -> str:
    if tipo == "factura":
        return "Factura electrónica de venta" if doc.get("estado_dian") == "aceptada" else "Factura de venta"
    if tipo == "pos":
        return "Documento equivalente POS"
    return "Nota crédito" if doc.get("tipo") == "credito" else "Nota débito"


def pdf_documento(tipo: str, doc: dict, empresa: dict, tercero: dict | None) -> bytes:
    """Representación gráfica del documento. Antes de la aceptación de la DIAN lo indica con una leyenda."""
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=estilos["Normal"], fontSize=9, leading=12)
    chico = ParagraphStyle("c", parent=normal, fontSize=7.5, leading=10, textColor=GRIS)
    fuerte = ParagraphStyle("f", parent=normal, fontName="Helvetica-Bold")
    grande = ParagraphStyle("g", parent=normal, fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=AZUL)

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=letter, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title=f"{_titulo(tipo, doc)} {doc.get('numero', '')}", author=empresa.get("razon_social", ""))
    el = []

    nit = f"NIT {empresa.get('nit', '')}" + (f"-{empresa['dv']}" if empresa.get("dv") else "")
    regimen = "Régimen SIMPLE de tributación" if empresa.get("regimen_tributario") == "SIMPLE" else "Régimen ordinario"
    izq = [Paragraph(f"<b>{empresa.get('razon_social', '')}</b>", ParagraphStyle("e", parent=normal, fontSize=12, leading=15)),
           Paragraph(f"{nit} · {regimen}", normal),
           Paragraph(" · ".join(x for x in (empresa.get("direccion"), empresa.get("ciudad"), empresa.get("telefono")) if x), chico)]
    der = [Paragraph(_titulo(tipo, doc), fuerte), Paragraph(str(doc.get("numero", "")), grande),
           Paragraph(f"Fecha: {doc.get('fecha', '')}" + (f" · Vence: {doc['fecha_vencimiento']}" if doc.get("fecha_vencimiento") else ""), normal)]
    cab = Table([[izq, der]], colWidths=[11 * cm, 6.8 * cm])
    cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1, AZUL), ("BOTTOMPADDING", (0, 0), (-1, 0), 8)]))
    el += [cab, Spacer(1, 8)]

    cliente = doc.get("cliente_nombre") or (tercero or {}).get("nombre") or "Consumidor final"
    ident = (tercero or {}).get("numero_documento", "")
    if ident and (tercero or {}).get("dv"):
        ident += f"-{tercero['dv']}"
    datos = [[Paragraph("<b>Cliente</b>", normal), Paragraph(cliente, normal), Paragraph("<b>Documento</b>", normal), Paragraph(f"{(tercero or {}).get('tipo_documento', '')} {ident}".strip(), normal)],
             [Paragraph("<b>Dirección</b>", normal), Paragraph(" ".join(x for x in ((tercero or {}).get("direccion"), (tercero or {}).get("ciudad")) if x), normal),
              Paragraph("<b>Correo</b>", normal), Paragraph((tercero or {}).get("email", "") or "", normal)]]
    if tipo == "nota":
        datos.append([Paragraph("<b>Factura origen</b>", normal), Paragraph(doc.get("factura_numero", ""), normal),
                      Paragraph("<b>Motivo</b>", normal), Paragraph(doc.get("motivo", ""), normal)])
    t = Table(datos, colWidths=[2.6 * cm, 6.9 * cm, 2.6 * cm, 5.7 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    el += [t, Spacer(1, 8)]

    filas = [["Descripción", "Cant.", "Valor unit.", "IVA %", "Total"]]
    for it in doc.get("items", []):
        filas.append([Paragraph(str(it.get("descripcion") or it.get("producto_nombre") or ""), normal), f"{it.get('cantidad', 0):g}",
                      _cop(it.get("precio_unitario")), f"{float(it.get('tarifa_iva', 0) or 0):g}", _cop(it.get("total", it.get("subtotal")))])
    tabla = Table(filas, colWidths=[7.4 * cm, 1.8 * cm, 3.2 * cm, 1.6 * cm, 3.8 * cm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]), ("LINEBELOW", (0, -1), (-1, -1), 0.5, GRIS)]))
    el += [tabla, Spacer(1, 6)]

    total = float(doc.get("total", 0) or 0)
    tot = [["Subtotal", _cop(doc.get("subtotal"))], ["IVA", _cop(doc.get("iva_total"))]]
    if doc.get("inc_total"):
        tot.append(["Impuesto al consumo", _cop(doc["inc_total"])])
    tot.append(["Total", _cop(total)])
    if doc.get("total_retenciones"):
        tot.append(["Retenciones que te practican", "-" + _cop(doc["total_retenciones"])])
        tot.append(["Neto a cobrar", _cop(doc.get("total_a_cobrar", doc.get("neto", total)))])
    tt = Table(tot, colWidths=[5.2 * cm, 3.6 * cm], hAlign="RIGHT")
    tt.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 3 if doc.get("inc_total") else 2), (-1, 3 if doc.get("inc_total") else 2), "Helvetica-Bold"),
                            ("LINEABOVE", (0, 3 if doc.get("inc_total") else 2), (-1, 3 if doc.get("inc_total") else 2), 0.5, GRIS)]))
    el += [tt, Spacer(1, 8), Paragraph(f"<b>{valor_en_letras(doc.get('total_a_cobrar', total) if doc.get('total_retenciones') else total)}</b>", normal)]

    if doc.get("observaciones"):
        el += [Spacer(1, 4), Paragraph(f"Observaciones: {doc['observaciones']}", normal)]
    el.append(Spacer(1, 14))
    if doc.get("cufe"):
        el.append(Paragraph(f"CUFE: {doc['cufe']}", chico))
    if tipo != "pos" and doc.get("estado_dian") != "aceptada":
        el.append(Paragraph("Documento pendiente de transmisión: no tiene validez como factura electrónica hasta su aceptación por la DIAN.", chico))
    pdf.build(el)
    return buf.getvalue()
