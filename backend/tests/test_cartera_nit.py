"""Dígito de verificación del NIT y cartera por edades / estado de cuenta."""
from core.nit import digito_verificacion
from tests.test_documentos import FECHA, _empresa, _preparar_ventas


def test_digito_verificacion_conocidos():
    assert digito_verificacion("900123456") == "8"
    assert digito_verificacion("860.002.964") == "4"  # Banco de Bogotá
    assert digito_verificacion("890903938") == "8"    # Bancolombia
    assert digito_verificacion("abc") is None


async def test_tercero_nit_calcula_y_valida_dv(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    base = {"nombre": "Acme SAS", "tipo": "cliente", "tipo_documento": "NIT"}
    r = await c.post("/api/configuracion/terceros", json={**base, "numero_documento": "900.123.456"})
    assert r.status_code == 201, r.text
    assert r.json()["dv"] == "8" and r.json()["numero_documento"] == "900123456"
    r = await c.post("/api/configuracion/terceros", json={**base, "nombre": "Otro", "numero_documento": "900123457", "dv": "1"})
    assert r.status_code == 422 and "dígito" in r.json()["detail"]
    r = await c.post("/api/configuracion/terceros", json={**base, "nombre": "Letras", "numero_documento": "ABC"})
    assert r.status_code == 422


async def test_antiguedad_y_estado_de_cuenta(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": "2026-05-01",
        "items": [{"producto_id": prod["id"], "cantidad": 20, "costo_unitario": 100}]})

    async def vender(valor, fecha, vence):
        r = await c.post("/api/facturacion/facturas", json={
            "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": fecha, "fecha_vencimiento": vence,
            "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": valor}]})
        assert r.status_code == 201, r.text
        return r.json()

    await vender(1000, "2026-06-01", "2026-06-30")   # 92 días de mora al 2026-10-01
    f2 = await vender(500, "2026-09-01", "2026-09-20")   # 11 días
    await vender(300, "2026-10-01", "2026-10-31")    # no vencido

    r = await c.get("/api/tesoreria/cartera/antiguedad", params={"tipo": "cxc", "corte": "2026-10-01"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["filas"]) == 1 and d["filas"][0]["documentos"] == 3
    assert d["totales"]["d90_mas"] == 1000 and d["totales"]["d1_30"] == 500 and d["totales"]["no_vencido"] == 300
    assert d["totales"]["total"] == 1800

    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    assert (await c.post("/api/tesoreria/pagos", json={
        "documento_tipo": "cxc", "documento_id": f2["id"], "cuenta_tipo": "caja", "cuenta_id": caja["id"],
        "fecha": "2026-10-01", "valor": 200})).status_code == 201

    e = (await c.get("/api/tesoreria/cartera/estado-cuenta", params={"tercero_id": cliente["id"], "tipo": "cxc"})).json()
    assert e["tercero"] == "Cliente Uno" and len(e["facturas"]) == 3 and len(e["pagos"]) == 1
    assert e["resumen"] == {"facturado": 1800, "pagado": 200, "saldo": 1600}
    assert {f["estado"] for f in e["facturas"]} == {"pendiente", "parcial"}
