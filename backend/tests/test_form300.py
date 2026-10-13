"""Formulario 300: liquidación del IVA del periodo."""
from tests.test_documentos import FECHA, _empresa, _preparar_ventas


async def test_form300_netea_notas_y_descuenta_compras(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    fac = (await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 2, "precio_unitario": 1000, "tarifa_iva": 19}]})).json()
    assert (await c.post("/api/facturacion/notas-credito-debito", json={
        "factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Descuento",
        "items": [{"descripcion": "Descuento", "precio_unitario": 500, "tarifa_iva": 19}]})).status_code == 201

    r = await c.get("/api/reportes/fiscales/form-300-iva", params={"desde": "2026-01-01", "hasta": "2026-12-31"})
    assert r.status_code == 200, r.text
    res = r.json()["resumen"]
    assert res["ventas_gravadas"] == 1500 and res["iva_generado"] == 285   # (2000-500) × 19 %
    assert res["saldo_a_pagar"] == 285 and res["saldo_a_favor"] == 0
