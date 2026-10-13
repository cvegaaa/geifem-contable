"""Total en letras, PDF, ZIP y envío al cliente de los documentos de venta."""
import io
import zipfile

from core import correo
from core.letras import valor_en_letras
from tests.test_documentos import FECHA, _empresa, _preparar_ventas


def test_valor_en_letras():
    casos = {
        0: "Son: cero pesos M/CTE", 1: "Son: un peso M/CTE", 21: "Son: veintiún pesos M/CTE",
        101000: "Son: ciento un mil pesos M/CTE", 1000000: "Son: un millón de pesos M/CTE",
        1200000: "Son: un millón doscientos mil pesos M/CTE", 2500000000: "Son: dos mil quinientos millones de pesos M/CTE",
        1500000.5: "Son: un millón quinientos mil pesos con cincuenta centavos M/CTE",
        1190: "Son: mil ciento noventa pesos M/CTE",
    }
    for valor, esperado in casos.items():
        assert valor_en_letras(valor) == esperado


async def _factura(c, nuevo_stock=True):
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA, "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    r = await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 2, "precio_unitario": 500, "tarifa_iva": 19}]})
    assert r.status_code == 201, r.text
    return r.json(), cliente


async def test_pdf_zip_y_envio_al_cliente(nuevo_cliente, monkeypatch):
    c, _ = await _empresa(nuevo_cliente)
    fac, cliente = await _factura(c)
    base = f"/api/facturacion/facturas/{fac['id']}"

    r = await c.get(f"{base}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and "Factura-FE1.pdf" in r.headers["content-disposition"]

    # El ZIP (PDF + XML) existe cuando la DIAN aceptó la factura y hay XML.
    assert (await c.get(f"{base}/zip")).status_code == 409
    from db import get_db
    from bson import ObjectId
    await get_db().facturas.update_one({"_id": ObjectId(fac["id"])}, {"$set": {"estado_dian": "aceptada", "xml": "<Invoice/>", "cufe": "abc"}})
    r = await c.get(f"{base}/zip")
    assert r.status_code == 200
    nombres = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert nombres == ["Factura-FE1.pdf", "Factura-FE1.xml"]

    # Envío por correo: sin SMTP responde 501; con él adjunta PDF y ZIP al correo del cliente.
    assert (await c.post(f"{base}/enviar-cliente", json={})).status_code == 422          # el cliente no tiene correo
    r = await c.post(f"{base}/enviar-cliente", json={"destinatario": "cliente@ejemplo.co"})
    assert r.status_code == 501 and "SMTP_HOST" in r.json()["detail"]

    enviados = []

    async def falso(destinatarios, asunto, cuerpo, adjuntos=None):
        enviados.append((destinatarios, asunto, cuerpo, [a[0] for a in (adjuntos or [])]))

    monkeypatch.setattr(correo, "enviar", falso)
    r = await c.post(f"{base}/enviar-cliente", json={"destinatario": "cliente@ejemplo.co", "mensaje": "Hola, su factura"})
    assert r.status_code == 200 and r.json() == {"enviado": True, "destinatario": "cliente@ejemplo.co"}
    destinatarios, asunto, cuerpo, adj = enviados[0]
    assert destinatarios == ["cliente@ejemplo.co"] and "FE1" in asunto and cuerpo.startswith("Hola, su factura")
    assert adj == ["Factura-FE1.pdf", "Factura-FE1.zip"]
    guardada = (await c.get(f"{base}")).json()
    assert guardada["envios_cliente"][0]["destinatario"] == "cliente@ejemplo.co"

    # Con correo en el tercero se usa por defecto; anulada no se envía.
    await c.put(f"/api/configuracion/terceros/{cliente['id']}", json={"email": "ana@ejemplo.co"})
    assert (await c.post(f"{base}/enviar-cliente", json={})).json()["destinatario"] == "ana@ejemplo.co"
    await get_db().facturas.update_one({"_id": ObjectId(fac["id"])}, {"$set": {"estado": "anulado"}})
    assert (await c.post(f"{base}/enviar-cliente", json={})).status_code == 409


async def test_pdf_de_pos_y_nota(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    fac, _ = await _factura(c)
    nota = (await c.post("/api/facturacion/notas-credito-debito", json={
        "factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Descuento",
        "items": [{"descripcion": "Descuento", "precio_unitario": 100}]})).json()
    r = await c.get(f"/api/facturacion/notas-credito-debito/{nota['id']}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and "Nota-NC-1.pdf" in r.headers["content-disposition"]
    assert (await c.get("/api/facturacion/facturas/000000000000000000000000/pdf")).status_code == 404
