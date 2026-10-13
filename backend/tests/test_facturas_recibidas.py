"""Facturas electrónicas recibidas: lectura del XML, eventos RADIAN y contabilización."""
from core.dian import ubl
from tests.test_documentos import _balance, _empresa

NIT_EMPRESA = "900111222"


def xml_factura(cufe="abc123", numero="SETP990000123", adquirente=NIT_EMPRESA, linea=1000.0, iva=19):
    valor_iva = round(linea * iva / 100, 2)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>{numero}</cbc:ID>
  <cbc:UUID schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
  <cbc:IssueDate>2026-10-01</cbc:IssueDate>
  <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
  <cac:PaymentMeans><cbc:PaymentDueDate>2026-10-31</cbc:PaymentDueDate></cac:PaymentMeans>
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyLegalEntity><cbc:RegistrationName>Proveedor Andino SAS</cbc:RegistrationName>
      <cbc:CompanyID schemeID="7" schemeName="31">860002964</cbc:CompanyID></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyLegalEntity><cbc:RegistrationName>Mi Empresa</cbc:RegistrationName>
      <cbc:CompanyID schemeID="1" schemeName="31">{adquirente}</cbc:CompanyID></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingCustomerParty>
  <cac:TaxTotal><cbc:TaxAmount currencyID="COP">{valor_iva}</cbc:TaxAmount>
    <cac:TaxSubtotal><cbc:TaxAmount currencyID="COP">{valor_iva}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:Percent>{iva}</cbc:Percent><cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal></cac:TaxTotal>
  <cac:LegalMonetaryTotal><cbc:LineExtensionAmount>{linea}</cbc:LineExtensionAmount>
    <cbc:PayableAmount>{linea + valor_iva}</cbc:PayableAmount></cac:LegalMonetaryTotal>
  <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="EA">2</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>{linea}</cbc:LineExtensionAmount>
    <cac:TaxTotal><cbc:TaxAmount>{valor_iva}</cbc:TaxAmount>
      <cac:TaxSubtotal><cbc:TaxAmount>{valor_iva}</cbc:TaxAmount>
        <cac:TaxCategory><cbc:Percent>{iva}</cbc:Percent><cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme></cac:TaxCategory>
      </cac:TaxSubtotal></cac:TaxTotal>
    <cac:Item><cbc:Description>Servicio de mantenimiento</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount>{linea / 2}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>""".encode("utf-8")


def archivo(contenido):
    return {"archivo": ("factura.xml", contenido, "application/xml")}


def test_lector_ubl_y_xml_peligroso():
    f = ubl.leer_factura(xml_factura())
    assert f["cufe"] == "abc123" and f["numero_factura"] == "SETP990000123" and f["fecha_vencimiento"] == "2026-10-31"
    assert f["proveedor"]["nit"] == "860002964" and f["proveedor"]["dv"] == "7"
    assert f["items"][0]["cantidad"] == 2 and f["items"][0]["costo_unitario"] == 500 and f["items"][0]["tarifa_iva"] == 19
    assert f["total_xml"] == 1190
    for malo in (b"<a/>", b"no es xml", b'<!DOCTYPE x [<!ENTITY y "z">]><Invoice/>'):
        try:
            ubl.leer_factura(malo)
            assert False
        except ubl.XmlInvalido:
            pass


async def test_cargar_eventos_y_contabilizar(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    # Vista previa: no guarda.
    r = await c.post("/api/compras/facturas-recibidas", params={"simular": "true"}, files=archivo(xml_factura()))
    assert r.status_code == 201 and not r.json()["guardada"] and r.json()["factura"]["proveedor_existente_id"] is None
    assert (await c.get("/api/compras/facturas-recibidas")).json() == []

    r = await c.post("/api/compras/facturas-recibidas", files=archivo(xml_factura()))
    assert r.status_code == 201, r.text
    fr = r.json()["factura"]
    assert fr["numero"] == "FR-1" and fr["estado_radian"] == "pendiente" and fr["total"] == 1190
    # El mismo CUFE no se carga dos veces; otro adquirente se rechaza.
    assert (await c.post("/api/compras/facturas-recibidas", files=archivo(xml_factura()))).status_code == 409
    assert (await c.post("/api/compras/facturas-recibidas", files=archivo(xml_factura(cufe="otro", adquirente="800123456")))).status_code == 409

    ev = f"/api/compras/facturas-recibidas/{fr['id']}/eventos"
    assert (await c.post(ev, json={"codigo": "033"})).status_code == 409                 # falta 030 y 032
    assert (await c.post(ev, json={"codigo": "030"})).status_code == 201
    assert (await c.post(ev, json={"codigo": "030"})).status_code == 409                 # repetido
    assert (await c.post(ev, json={"codigo": "033"})).status_code == 409                 # falta 032
    assert (await c.post(ev, json={"codigo": "031"})).status_code == 422                 # reclamo sin motivo
    assert (await c.post(ev, json={"codigo": "032"})).status_code == 201
    r = await c.post(ev, json={"codigo": "033"})
    assert r.status_code == 201 and r.json()["estado_radian"] == "aceptada"
    assert (await c.post(ev, json={"codigo": "031", "motivo": "01"})).status_code == 409  # ya aceptada
    assert all(e["transmision"] == "pendiente" for e in r.json()["eventos"])

    r = await c.post(f"/api/compras/facturas-recibidas/{fr['id']}/contabilizar",
                     json={"afecta_inventario": False, "cuenta_gasto": "5135", "aplicar_reteiva": False})
    assert r.status_code == 201, r.text
    fp = r.json()
    assert fp["numero"] == "FP-1" and fp["cufe"] == "abc123" and fp["total"] == 1190 and fp["proveedor_nombre"] == "Proveedor Andino SAS"
    b = await _balance(c)
    assert b["5135"] == 1000 and b["2205"] == -1190 and b["2408"] == 190
    prov = [t for t in (await c.get("/api/configuracion/terceros")).json() if t["numero_documento"] == "860002964"][0]
    assert prov["tipo"] == "proveedor" and prov["dv"] == "7"
    assert (await c.post(f"/api/compras/facturas-recibidas/{fr['id']}/contabilizar", json={})).status_code == 409

    # Anular la factura de proveedor libera la recibida para contabilizarla de nuevo.
    assert (await c.post(f"/api/compras/facturas-proveedor/{fp['id']}/anular", json={})).status_code == 200
    again = (await c.get(f"/api/compras/facturas-recibidas/{fr['id']}")).json()
    assert again["contabilizada"] is False and again["factura_proveedor_id"] is None


async def test_reclamo_bloquea_contabilizacion(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    fr = (await c.post("/api/compras/facturas-recibidas", files=archivo(xml_factura(cufe="z9")))).json()["factura"]
    ev = f"/api/compras/facturas-recibidas/{fr['id']}/eventos"
    assert (await c.post(ev, json={"codigo": "030"})).status_code == 201
    assert (await c.post(ev, json={"codigo": "031", "motivo": "02", "observaciones": "No llegó"})).status_code == 201
    assert (await c.post(ev, json={"codigo": "033"})).status_code == 409
    r = await c.post(f"/api/compras/facturas-recibidas/{fr['id']}/contabilizar", json={})
    assert r.status_code == 409 and "reclamo" in r.json()["detail"]
