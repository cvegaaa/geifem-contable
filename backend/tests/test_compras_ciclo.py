"""Ciclo de compras: seguimiento de la orden, límites de recepción y facturación, y devoluciones a proveedor."""
from tests.test_documentos import FECHA, _balance, _empresa, _existencia, _preparar_ventas


async def _orden(c, proveedor, bodega, prod, cantidad=10, costo=100):
    r = await c.post("/api/compras/ordenes-compra", json={
        "proveedor_id": proveedor["id"], "fecha": FECHA, "bodega_id": bodega["id"],
        "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": cantidad, "costo_unitario": costo}]})
    assert r.status_code == 201, r.text
    return r.json()


def _entrada(orden, bodega, prod, cantidad, costo=100):
    return {"orden_compra_id": orden["id"], "bodega_id": bodega["id"], "fecha": FECHA,
            "items": [{"producto_id": prod["id"], "cantidad": cantidad, "costo_unitario": costo}]}


async def _estado(c, orden):
    return (await c.get(f"/api/compras/ordenes-compra/{orden['id']}")).json()["estado"]


async def test_orden_parcial_recibida_y_limites(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, _, proveedor, _, bodega = await _preparar_ventas(c)
    oc = await _orden(c, proveedor, bodega, prod)

    r1 = await c.post("/api/compras/recepcion-mercancia", json=_entrada(oc, bodega, prod, 6))
    assert r1.status_code == 201, r1.text
    assert await _estado(c, oc) == "parcial"
    pend = (await c.get(f"/api/compras/ordenes-compra/{oc['id']}/pendiente")).json()
    assert pend[0]["pedido"] == 10 and pend[0]["recibido"] == 6 and pend[0]["pendiente"] == 4
    # No se recibe más de lo pendiente.
    assert (await c.post("/api/compras/recepcion-mercancia", json=_entrada(oc, bodega, prod, 5))).status_code == 409
    r2 = await c.post("/api/compras/recepcion-mercancia", json=_entrada(oc, bodega, prod, 4))
    assert r2.status_code == 201 and await _estado(c, oc) == "recibida"
    # Editar la primera entrada no cuenta su cantidad dos veces.
    assert (await c.put(f"/api/compras/recepcion-mercancia/{r1.json()['id']}", json=_entrada(oc, bodega, prod, 6))).status_code == 200
    # Anular una entrada devuelve la orden a parcial.
    assert (await c.post(f"/api/compras/recepcion-mercancia/{r2.json()['id']}/anular", json={})).status_code == 200
    assert await _estado(c, oc) == "parcial"

    # Cerrar con pendiente: no admite más entradas.
    assert (await c.post(f"/api/compras/ordenes-compra/{oc['id']}/cerrar", json={"motivo": "El proveedor no envía el resto"})).status_code == 200
    assert await _estado(c, oc) == "cerrada"
    assert (await c.post("/api/compras/recepcion-mercancia", json=_entrada(oc, bodega, prod, 1))).status_code == 409


async def test_factura_solo_de_lo_recibido(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, _, proveedor, _, bodega = await _preparar_ventas(c)
    oc = await _orden(c, proveedor, bodega, prod)
    await c.post("/api/compras/recepcion-mercancia", json=_entrada(oc, bodega, prod, 6))

    def factura(numero, cant):
        return {"proveedor_id": proveedor["id"], "numero_factura": numero, "fecha": FECHA, "orden_compra_id": oc["id"],
                "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": cant, "costo_unitario": 100}]}

    assert (await c.post("/api/compras/facturas-proveedor", json=factura("F-1", 8))).status_code == 409
    assert (await c.post("/api/compras/facturas-proveedor", json=factura("F-1", 4))).status_code == 201
    assert (await c.post("/api/compras/facturas-proveedor", json=factura("F-2", 3))).status_code == 409   # solo quedan 2
    assert (await c.post("/api/compras/facturas-proveedor", json=factura("F-2", 2))).status_code == 201


async def test_devolucion_a_proveedor_revierte_inventario_iva_y_saldo(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, _, proveedor, _, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA, "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    fp = (await c.post("/api/compras/facturas-proveedor", json={
        "proveedor_id": proveedor["id"], "numero_factura": "F-9", "fecha": FECHA, "aplicar_reteiva": False,
        "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": 10, "costo_unitario": 100, "tarifa_iva": 19}]})).json()
    assert fp["saldo_pendiente"] == 1190
    antes = await _balance(c)

    cuerpo = {"factura_id": fp["id"], "fecha": FECHA, "motivo": "Defecto",
              "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": 3, "costo_unitario": 100, "tarifa_iva": 19}]}
    r = await c.post("/api/compras/devoluciones-proveedor", json=cuerpo)
    assert r.status_code == 201, r.text
    dev = r.json()
    assert dev["numero"] == "NP-1" and dev["total"] == 357 and dev["neto"] == 357
    assert await _existencia(c, prod["id"]) == 7
    despues = await _balance(c)
    assert despues["2205"] - antes["2205"] == 357       # baja la deuda con el proveedor (saldo crédito menos negativo)
    assert despues["1435"] - antes["1435"] == -300      # sale la mercancía
    assert despues["2408"] - antes["2408"] == -57       # se revierte el IVA descontable
    assert (await c.get("/api/compras/facturas-proveedor")).json()[0]["saldo_pendiente"] == 833

    # No se devuelve más de lo facturado y la factura queda bloqueada mientras haya devoluciones.
    assert (await c.post("/api/compras/devoluciones-proveedor", json={**cuerpo, "items": [{**cuerpo["items"][0], "cantidad": 8}]})).status_code == 409
    assert (await c.post(f"/api/compras/facturas-proveedor/{fp['id']}/anular", json={})).status_code == 409

    assert (await c.post(f"/api/compras/devoluciones-proveedor/{dev['id']}/anular", json={})).status_code == 200
    assert await _existencia(c, prod["id"]) == 10
    assert (await c.get("/api/compras/facturas-proveedor")).json()[0]["saldo_pendiente"] == 1190
    assert await _balance(c) == antes


async def test_devolucion_prorratea_reteiva(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, _, proveedor, _, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA, "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    fp = (await c.post("/api/compras/facturas-proveedor", json={
        "proveedor_id": proveedor["id"], "numero_factura": "F-10", "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": 10, "costo_unitario": 100, "tarifa_iva": 19}]})).json()
    assert fp["retenciones"]["reteiva"] == 28.5 and fp["saldo_pendiente"] == 1161.5
    dev = (await c.post("/api/compras/devoluciones-proveedor", json={
        "factura_id": fp["id"], "fecha": FECHA, "motivo": "Defecto",
        "items": [{"producto_id": prod["id"], "descripcion": "Camisa", "cantidad": 5, "costo_unitario": 100, "tarifa_iva": 19}]})).json()
    assert dev["total"] == 595 and dev["total_retenciones"] == 14.25 and dev["neto"] == 580.75
    assert (await c.get("/api/compras/facturas-proveedor")).json()[0]["saldo_pendiente"] == 580.75
