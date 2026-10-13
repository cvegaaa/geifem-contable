"""Nota crédito por devolución: reingreso a inventario al costo de venta."""
from tests.test_documentos import FECHA, _balance, _empresa, _existencia, _preparar_ventas


async def test_devolucion_reingresa_inventario_y_reversa_costo(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    fac = (await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 4, "precio_unitario": 500}]})).json()
    assert await _existencia(c, prod["id"]) == 6
    antes = await _balance(c)
    assert antes["6135"] == 400 and antes["1435"] == 600

    def nota(cant, reingresar=True):
        return {"factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Devolución",
                "items": [{"descripcion": "Camisa", "producto_id": prod["id"], "cantidad": cant,
                           "precio_unitario": 500, "reingresar": reingresar}]}

    r = await c.post("/api/facturacion/notas-credito-debito", json=nota(1))
    assert r.status_code == 201, r.text
    nc = r.json()
    assert await _existencia(c, prod["id"]) == 7
    despues = await _balance(c)
    assert despues["6135"] == 300 and despues["1435"] == 700   # costo y existencias de 1 unidad a $100

    # No se puede devolver más de lo vendido (4 vendidas, 1 ya devuelta).
    assert (await c.post("/api/facturacion/notas-credito-debito", json=nota(4))).status_code == 409
    # Editar la propia nota no cuenta dos veces su cantidad.
    assert (await c.put(f"/api/facturacion/notas-credito-debito/{nc['id']}", json=nota(3))).status_code == 200
    assert await _existencia(c, prod["id"]) == 9

    assert (await c.post(f"/api/facturacion/notas-credito-debito/{nc['id']}/anular", json={})).status_code == 200
    assert await _existencia(c, prod["id"]) == 6
    assert (await _balance(c))["6135"] == 400
