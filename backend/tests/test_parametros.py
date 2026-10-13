"""Parametrización contable: cuentas por empresa, producto, caja y banco."""
from tests.conftest import registrar

FECHA = "2026-10-01"
RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


async def _empresa(nuevo_cliente):
    c = nuevo_cliente()
    await registrar(c, "dueno@a.co", "900111222")
    return c


async def _balance(c) -> dict:
    r = await c.get("/api/reportes/contables/balance-de-prueba", params=RANGO)
    return {f["codigo"]: f["saldo"] for f in r.json()["filas"]}


async def _subcuenta(c, codigo, nombre, naturaleza="debito"):
    r = await c.post("/api/configuracion/plan-cuentas", json={
        "codigo": codigo, "nombre": nombre, "naturaleza": naturaleza, "acepta_movimientos": True})
    assert r.status_code == 201, r.text


async def _datos_venta(c, **cuentas_producto):
    prod = (await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "Camiseta", "sku": "CAM-1", **cuentas_producto})).json()
    cliente = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Cliente", "tipo": "cliente", "numero_documento": "1001"})).json()
    resol = (await c.post("/api/configuracion/resoluciones-dian", json={
        "numero_resolucion": "1876", "prefijo": "FE", "rango_desde": 1, "rango_hasta": 100,
        "fecha_inicio": "2026-01-01", "fecha_fin": "2027-12-31"})).json()
    bodega = (await c.get("/api/inventario/bodegas")).json()[0]
    return prod, cliente, resol, bodega


async def test_cuentas_propias_del_producto(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await _subcuenta(c, "143505", "Inventario camisetas")
    await _subcuenta(c, "413505", "Venta de camisetas", "credito")
    await _subcuenta(c, "613505", "Costo camisetas")
    prod, cliente, resol, bodega = await _datos_venta(
        c, cuenta_inventario="143505", cuenta_ingreso="413505", cuenta_costo="613505")

    r = await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    assert r.status_code == 201, r.text
    r = await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 4, "precio_unitario": 300}]})
    assert r.status_code == 201, r.text

    saldos = await _balance(c)
    assert saldos["143505"] == 600      # 1000 que entraron - 400 vendidos al costo
    assert saldos["2335"] == -1000      # mercancía recibida pendiente de factura del proveedor
    assert saldos["413505"] == -1200
    assert saldos["613505"] == 400
    assert "1435" not in saldos and "4135" not in saldos


async def test_parametros_de_empresa_y_pago_con_la_cuenta_original(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await _subcuenta(c, "130505", "Clientes nacionales")
    params = {p["clave"]: p["codigo"] for p in (await c.get("/api/configuracion/parametros-contables")).json()}
    assert params["clientes"] == "1305" and params["inventario"] == "1435"

    r = await c.put("/api/configuracion/parametros-contables", json={"cuentas": {"clientes": "130505"}})
    assert r.status_code == 200, r.text
    prod, cliente, resol, _ = await _datos_venta(c, inventariable=False)
    fac = (await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": 1000}]})).json()
    assert (await _balance(c))["130505"] == 1000

    # Aunque luego se vuelva a 1305, el cobro cruza contra la cuenta con que se facturó.
    await c.put("/api/configuracion/parametros-contables", json={"cuentas": {"clientes": "1305"}})
    caja = (await c.get("/api/tesoreria/caja")).json()[0]
    r = await c.post("/api/tesoreria/pagos", json={
        "documento_tipo": "cxc", "documento_id": fac["id"], "cuenta_tipo": "caja",
        "cuenta_id": caja["id"], "fecha": FECHA, "valor": 1000})
    assert r.status_code == 201, r.text
    saldos = await _balance(c)
    assert "130505" not in saldos or saldos["130505"] == 0
    assert "1305" not in saldos


async def test_validaciones_de_cuentas(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    r = await c.put("/api/configuracion/parametros-contables", json={"cuentas": {"clientes": "13"}})
    assert r.status_code == 422 and "agrupación" in r.json()["detail"]
    r = await c.put("/api/configuracion/parametros-contables", json={"cuentas": {"clientes": "999999"}})
    assert r.status_code == 422
    r = await c.post("/api/inventario/catalogo-productos", json={"nombre": "X", "sku": "X", "cuenta_ingreso": "4"})
    assert r.status_code == 422
    r = await c.post("/api/tesoreria/cuentas-bancarias", json={"nombre": "Banco", "cuenta_contable": "11"})
    assert r.status_code == 422


async def test_caja_con_cuenta_propia_y_pos(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    cajas = (await c.get("/api/tesoreria/caja")).json()
    assert [x["nombre"] for x in cajas] == ["Caja general"]  # se crea con la empresa

    await _subcuenta(c, "110510", "Caja menor")
    menor = (await c.post("/api/tesoreria/cuentas-caja", json={
        "nombre": "Caja menor", "cuenta_contable": "110510"})).json()
    r = await c.post("/api/tesoreria/movimientos", json={
        "cuenta_tipo": "caja", "cuenta_id": menor["id"], "tipo": "egreso", "fecha": FECHA,
        "valor": 50, "concepto": "Papelería", "cuenta_contrapartida": "5195"})
    assert r.status_code == 201, r.text

    pos = (await c.post("/api/facturacion/documento-equivalente-pos", json={
        "fecha": FECHA, "caja_id": menor["id"],
        "items": [{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 200}]})).json()
    assert pos["caja_nombre"] == "Caja menor"
    saldos = await _balance(c)
    assert saldos["110510"] == 150 and "1105" not in saldos
    saldo_caja = {x["nombre"]: x["saldo"] for x in (await c.get("/api/tesoreria/caja")).json()}
    assert saldo_caja["Caja menor"] == 150   # el POS entra al saldo de la caja

    await c.post(f"/api/facturacion/documento-equivalente-pos/{pos['id']}/anular", json={})
    saldo_caja = {x["nombre"]: x["saldo"] for x in (await c.get("/api/tesoreria/caja")).json()}
    assert saldo_caja["Caja menor"] == -50


async def test_ajustes_de_inventario_contabilizan(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    prod, _, _, bodega = await _datos_venta(c)
    base = {"producto_id": prod["id"], "bodega_id": bodega["id"], "fecha": FECHA}

    r = await c.post("/api/inventario/kardex/movimientos", json={**base, "tipo": "entrada", "cantidad": 10, "costo_unitario": 100})
    assert r.status_code == 201, r.text
    faltante = (await c.post("/api/inventario/kardex/movimientos", json={**base, "tipo": "ajuste", "cantidad": 7})).json()
    assert faltante["diferencia"] == -3 and faltante["valor"] == 300

    saldos = await _balance(c)
    assert saldos["1435"] == 700          # 1000 sobrante inicial - 300 faltante
    assert saldos["4295"] == -1000
    assert saldos["5195"] == 300

    await c.post(f"/api/inventario/kardex/ajustes/{faltante['id']}/anular", json={})
    assert (await _balance(c))["1435"] == 1000
