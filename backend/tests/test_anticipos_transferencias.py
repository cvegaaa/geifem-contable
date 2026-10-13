"""Anticipos, pagos que cubren varias facturas y transferencias entre cajas y bancos."""
from tests.test_documentos import FECHA, _balance, _empresa, _preparar_ventas


async def _facturar(c, prod, cliente, resol, valor, fecha=FECHA):
    r = await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": fecha,
        "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": valor}]})
    assert r.status_code == 201, r.text
    return r.json()


async def _saldo(c, lista, cuenta):
    ruta = "caja" if lista == "caja" else "bancos"
    return next(x["saldo"] for x in (await c.get(f"/api/tesoreria/{ruta}")).json() if x["id"] == cuenta["id"])


async def _con_stock(c):
    prod, cliente, proveedor, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": "2026-05-01",
        "items": [{"producto_id": prod["id"], "cantidad": 20, "costo_unitario": 10}]})
    return prod, cliente, proveedor, resol


async def test_anticipo_de_cliente_se_aplica_y_se_revierte(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol = await _con_stock(c)
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    fac = await _facturar(c, prod, cliente, resol, 1000)

    r = await c.post("/api/tesoreria/anticipos", json={
        "tipo": "cliente", "tercero_id": cliente["id"], "fecha": FECHA, "valor": 600,
        "cuenta_tipo": "caja", "cuenta_id": caja["id"]})
    assert r.status_code == 201, r.text
    ant = r.json()
    assert ant["numero"] == "AC-1" and ant["saldo"] == 600
    assert await _saldo(c, "caja", caja) == 600
    assert (await _balance(c))["2805"] == -600     # pasivo con saldo crédito

    # Aplicación parcial: baja el saldo de la factura y el del anticipo; no mueve efectivo.
    assert (await c.post(f"/api/tesoreria/anticipos/{ant['id']}/aplicar", json={
        "documento_id": fac["id"], "fecha": FECHA, "valor": 700})).status_code == 409
    r = await c.post(f"/api/tesoreria/anticipos/{ant['id']}/aplicar", json={
        "documento_id": fac["id"], "fecha": FECHA, "valor": 400})
    assert r.status_code == 201, r.text
    ap = r.json()
    assert ap["numero"] == "AA-1" and ap["saldo_resultante"] == 600
    assert await _saldo(c, "caja", caja) == 600
    assert (await _balance(c))["2805"] == -200
    # Con aplicaciones activas no se anula.
    assert (await c.post(f"/api/tesoreria/anticipos/{ant['id']}/anular", json={})).status_code == 409

    assert (await c.post(f"/api/tesoreria/aplicaciones-anticipo/{ap['id']}/anular", json={})).status_code == 200
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 1000
    assert (await c.post(f"/api/tesoreria/anticipos/{ant['id']}/anular", json={})).status_code == 200
    assert await _saldo(c, "caja", caja) == 0
    assert (await _balance(c)).get("2805", 0) == 0


async def test_anticipo_a_proveedor_exige_mismo_tercero(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, proveedor, resol = await _con_stock(c)
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    await c.post("/api/tesoreria/movimientos", json={
        "cuenta_tipo": "caja", "cuenta_id": caja["id"], "tipo": "ingreso", "fecha": "2026-05-01",
        "valor": 5000, "concepto": "Fondeo", "cuenta_contrapartida": "3105"})
    r = await c.post("/api/tesoreria/anticipos", json={
        "tipo": "proveedor", "tercero_id": proveedor["id"], "fecha": FECHA, "valor": 300,
        "cuenta_tipo": "caja", "cuenta_id": caja["id"]})
    assert r.status_code == 201 and r.json()["numero"] == "AD-1"
    assert (await _balance(c))["1330"] == 300
    fac = await _facturar(c, prod, cliente, resol, 500)
    # Una factura de venta no es del proveedor: se rechaza el cruce.
    ant = r.json()
    assert (await c.post(f"/api/tesoreria/anticipos/{ant['id']}/aplicar", json={
        "documento_id": fac["id"], "fecha": FECHA, "valor": 100})).status_code in (404, 409)


async def test_pago_multiple_y_transferencia(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol = await _con_stock(c)
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    banco = (await c.post("/api/tesoreria/cuentas-bancarias", json={"nombre": "Banco", "banco": "X", "numero_cuenta": "1"})).json()
    f1, f2 = await _facturar(c, prod, cliente, resol, 1000), await _facturar(c, prod, cliente, resol, 500)

    r = await c.post("/api/tesoreria/pagos/multiple", json={
        "documento_tipo": "cxc", "cuenta_tipo": "caja", "cuenta_id": caja["id"], "fecha": FECHA,
        "aplicaciones": [{"documento_id": f1["id"], "valor": 1000}, {"documento_id": f2["id"], "valor": 200}]})
    assert r.status_code == 201, r.text
    pagos = r.json()
    assert [p["numero"] for p in pagos] == ["RC-1", "RC-2"] and pagos[0]["lote"] == pagos[1]["lote"]
    assert await _saldo(c, "caja", caja) == 1200
    # Si una aplicación falla, no se guarda ninguna.
    r = await c.post("/api/tesoreria/pagos/multiple", json={
        "documento_tipo": "cxc", "cuenta_tipo": "caja", "cuenta_id": caja["id"], "fecha": FECHA,
        "aplicaciones": [{"documento_id": f2["id"], "valor": 100}, {"documento_id": f1["id"], "valor": 1}]})
    assert r.status_code == 409
    assert (await c.get(f"/api/facturacion/facturas/{f2['id']}")).json()["saldo_pendiente"] == 300

    r = await c.post("/api/tesoreria/transferencias", json={
        "origen_tipo": "caja", "origen_id": caja["id"], "destino_tipo": "banco", "destino_id": banco["id"],
        "fecha": FECHA, "valor": 1000})
    assert r.status_code == 201, r.text
    tr = r.json()
    assert tr["numero"] == "TR-1"
    assert await _saldo(c, "caja", caja) == 200
    assert await _saldo(c, "banco", banco) == 1000
    b = await _balance(c)
    assert b["1105"] == 200 and b["1110"] == 1000
    mismo = {"origen_tipo": "caja", "origen_id": caja["id"], "destino_tipo": "caja", "destino_id": caja["id"],
             "fecha": FECHA, "valor": 1}
    assert (await c.post("/api/tesoreria/transferencias", json=mismo)).status_code == 422

    flujo = (await c.get("/api/tesoreria/flujo-caja", params={"desde": "2026-01-01", "hasta": "2026-12-31"})).json()
    assert flujo["resumen"]["ingresos"] == 1200      # la transferencia no cuenta como ingreso ni egreso
    assert (await c.post(f"/api/tesoreria/transferencias/{tr['id']}/anular", json={})).status_code == 200
    assert await _saldo(c, "banco", banco) == 0
