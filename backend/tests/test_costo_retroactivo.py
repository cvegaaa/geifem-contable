"""El costo de venta se corrige cuando una compra con fecha anterior cambia el costo promedio."""
from tests.test_documentos import _balance, _empresa, _existencia, _preparar_ventas


async def test_compra_con_fecha_anterior_ajusta_costo_de_venta(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)

    async def entrada(fecha, cantidad, costo):
        r = await c.post("/api/compras/recepcion-mercancia", json={
            "bodega_id": bodega["id"], "fecha": fecha, "items": [{"producto_id": prod["id"], "cantidad": cantidad, "costo_unitario": costo}]})
        assert r.status_code == 201, r.text
        return r.json()

    await entrada("2026-10-01", 10, 100)
    r = await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": "2026-10-02",
        "items": [{"producto_id": prod["id"], "cantidad": 5, "precio_unitario": 500}]})
    assert r.status_code == 201, r.text
    fac = r.json()
    b = await _balance(c)
    assert b["6135"] == 500 and b["1435"] == 500

    # Llega (registrada tarde) una compra de septiembre a otro costo: el promedio de la fecha de la venta cambia.
    tarde = await entrada("2026-09-15", 10, 200)
    b = await _balance(c)
    assert b["6135"] == 750 and b["1435"] == 2250       # 15 unidades restantes a 150 = valor del kardex
    existencias = await _existencia(c, prod["id"])
    assert existencias == 15

    # Anular esa compra deja el costo como estaba.
    assert (await c.post(f"/api/compras/recepcion-mercancia/{tarde['id']}/anular", json={})).status_code == 200
    b = await _balance(c)
    assert b["6135"] == 500 and b["1435"] == 500

    # Anular la venta limpia también cualquier ajuste.
    await entrada("2026-09-15", 10, 200)
    assert (await c.post(f"/api/facturacion/facturas/{fac['id']}/anular", json={})).status_code == 200
    b = await _balance(c)
    assert b.get("6135", 0) == 0 and b["1435"] == 3000
