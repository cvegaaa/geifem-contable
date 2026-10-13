"""Ciclo de vida de documentos: numeración, edición, anulación y efectos."""
import asyncio

from tests.conftest import registrar

FECHA = "2026-10-01"
RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


async def _empresa(nuevo_cliente):
    c = nuevo_cliente()
    await registrar(c, "dueno@a.co", "900111222")
    cuentas = {x["codigo"]: x["id"] for x in (await c.get("/api/configuracion/plan-cuentas")).json()}
    return c, cuentas


async def _balance(c) -> dict:
    r = await c.get("/api/reportes/contables/balance-de-prueba", params=RANGO)
    assert r.status_code == 200, r.text
    return {f["codigo"]: f["saldo"] for f in r.json()["filas"]}


def _comprobante(cuentas, valor, estado="contabilizado"):
    return {"tipo": "ajuste", "fecha": FECHA, "estado": estado, "descripcion": "Aporte",
            "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": valor},
                       {"cuenta_puc_id": cuentas["3105"], "credito": valor}]}


async def test_comprobante_numerado_editable_y_anulable(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)

    r = await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, 1000))
    assert r.status_code == 201, r.text
    comp = r.json()
    assert comp["numero"] == "CA-1"
    # Contabilizado => llega al libro y a los reportes.
    assert (await _balance(c))["1105"] == 1000

    r = await c.put(f"/api/contabilidad/comprobantes/{comp['id']}", json=_comprobante(cuentas, 2500))
    assert r.status_code == 200, r.text
    assert r.json()["numero"] == "CA-1"
    assert (await _balance(c))["1105"] == 2500

    r = await c.post(f"/api/contabilidad/comprobantes/{comp['id']}/anular", json={"motivo": "error"})
    assert r.json()["estado"] == "anulado"
    assert "1105" not in await _balance(c)
    # Un anulado no se edita, y el número no se reutiliza.
    assert (await c.put(f"/api/contabilidad/comprobantes/{comp['id']}", json=_comprobante(cuentas, 1))).status_code == 409
    r = await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, 10, "borrador"))
    assert r.json()["numero"] == "CA-2"
    assert "1105" not in await _balance(c)  # borrador no afecta el libro

    auditoria = (await c.get("/api/contabilidad/auditoria", params={"documento_id": comp["id"]})).json()
    assert [a["accion"] for a in auditoria] == ["anulado", "editado", "creado"]


async def test_comprobante_rechaza_cuentas_de_agrupacion(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    cuerpo = _comprobante(cuentas, 100)
    cuerpo["lineas"][0]["cuenta_puc_id"] = cuentas["11"]
    r = await c.post("/api/contabilidad/comprobantes", json=cuerpo)
    assert r.status_code == 422
    assert "agrupación" in r.json()["detail"]


async def test_numeracion_sin_duplicados_en_concurrencia(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    respuestas = await asyncio.gather(
        *[c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, 1)) for _ in range(8)]
    )
    assert all(r.status_code == 201 for r in respuestas), [r.text for r in respuestas]
    assert sorted(r.json()["consecutivo"] for r in respuestas) == list(range(1, 9))


async def _preparar_ventas(c):
    prod = (await c.post("/api/inventario/catalogo-productos", json={"nombre": "Camisa", "sku": "CAM-1"})).json()
    cliente = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Cliente Uno", "tipo": "cliente", "numero_documento": "1001"})).json()
    proveedor = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor Uno", "tipo": "proveedor", "numero_documento": "2002"})).json()
    resol = (await c.post("/api/configuracion/resoluciones-dian", json={
        "numero_resolucion": "18760000001", "prefijo": "FE", "rango_desde": 1, "rango_hasta": 1000,
        "fecha_inicio": "2026-01-01", "fecha_fin": "2027-12-31"})).json()
    bodega = (await c.get("/api/inventario/bodegas")).json()[0]
    return prod, cliente, proveedor, resol, bodega


async def _existencia(c, producto_id) -> float:
    filas = (await c.get("/api/inventario/kardex/existencias", params={"producto_id": producto_id})).json()
    return sum(f["cantidad"] for f in filas)


async def test_kardex_ventas_y_anulaciones(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)

    async def entrada(cant, costo):
        r = await c.post("/api/compras/recepcion-mercancia", json={
            "bodega_id": bodega["id"], "fecha": FECHA,
            "items": [{"producto_id": prod["id"], "cantidad": cant, "costo_unitario": costo}]})
        assert r.status_code == 201, r.text
        return r.json()

    e1 = await entrada(10, 100)
    e2 = await entrada(10, 200)
    assert e2["numero"] == "EM-2"
    assert await _existencia(c, prod["id"]) == 20

    factura = {"cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": "2026-10-02",
               "items": [{"producto_id": prod["id"], "cantidad": 5, "precio_unitario": 300, "tarifa_iva": 19}]}
    r = await c.post("/api/facturacion/facturas", json=factura)
    assert r.status_code == 201, r.text
    fac = r.json()
    assert fac["numero"] == "FE1"
    assert await _existencia(c, prod["id"]) == 15
    saldos = await _balance(c)
    assert saldos["6135"] == 750       # 5 unidades a costo promedio 150
    assert saldos["4135"] == -1500
    assert saldos["2408"] == -285

    # Editar la factura ajusta inventario y libro.
    factura["items"][0]["cantidad"] = 6
    r = await c.put(f"/api/facturacion/facturas/{fac['id']}", json=factura)
    assert r.status_code == 200, r.text
    assert await _existencia(c, prod["id"]) == 14
    assert (await _balance(c))["4135"] == -1800

    # Anular la primera entrada sigue siendo posible (quedan 10 para cubrir 6 vendidas)...
    r = await c.post(f"/api/compras/recepcion-mercancia/{e1['id']}/anular", json={})
    assert r.status_code == 200, r.text
    assert await _existencia(c, prod["id"]) == 4
    # ...pero anular también la segunda dejaría existencias negativas.
    r = await c.post(f"/api/compras/recepcion-mercancia/{e2['id']}/anular", json={})
    assert r.status_code == 409
    assert "insuficiente" in r.json()["detail"]
    assert await _existencia(c, prod["id"]) == 4  # la transacción revirtió todo

    # Vender más de lo que hay se rechaza.
    factura["items"][0]["cantidad"] = 50
    r = await c.post("/api/facturacion/facturas", json=factura)
    assert r.status_code == 409


async def test_factura_con_pagos_y_notas(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    fac = (await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 2, "precio_unitario": 500}]})).json()
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja general"})).json()

    nota = {"factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Descuento",
            "items": [{"descripcion": "Descuento", "precio_unitario": 200}]}
    r = await c.post("/api/facturacion/notas-credito-debito", json=nota)
    assert r.status_code == 201, r.text
    nc = r.json()
    assert nc["numero"] == "NC-1"

    pago = {"documento_tipo": "cxc", "documento_id": fac["id"], "cuenta_tipo": "caja",
            "cuenta_id": caja["id"], "fecha": FECHA, "valor": 800}
    r = await c.post("/api/tesoreria/pagos", json=pago)
    assert r.status_code == 201, r.text
    rc = r.json()
    assert rc["numero"] == "RC-1"
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 0
    assert (await c.post("/api/tesoreria/pagos", json={**pago, "valor": 1})).status_code == 409

    # Con pagos o notas activas la factura no se toca.
    assert (await c.post(f"/api/facturacion/facturas/{fac['id']}/anular", json={})).status_code == 409

    assert (await c.post(f"/api/tesoreria/pagos/{rc['id']}/anular", json={})).status_code == 200
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 800
    assert (await c.get("/api/tesoreria/caja")).json()[0]["saldo"] == 0
    assert (await c.post(f"/api/facturacion/notas-credito-debito/{nc['id']}/anular", json={})).status_code == 200
    assert (await c.post(f"/api/facturacion/facturas/{fac['id']}/anular", json={})).status_code == 200
    assert await _existencia(c, prod["id"]) == 10
    assert (await c.get("/api/tesoreria/cxc-cxp")).json()["cxc"] == []


async def test_factura_proveedor_no_se_duplica(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    _, _, proveedor, _, _ = await _preparar_ventas(c)
    cuerpo = {"proveedor_id": proveedor["id"], "numero_factura": "A-77", "fecha": FECHA,
              "afecta_inventario": False, "cuenta_gasto": "5135",
              "items": [{"descripcion": "Servicio", "cantidad": 1, "costo_unitario": 1000}]}
    r = await c.post("/api/compras/facturas-proveedor", json=cuerpo)
    assert r.status_code == 201, r.text
    assert r.json()["numero"] == "FP-1"
    assert (await c.post("/api/compras/facturas-proveedor", json=cuerpo)).status_code == 409
    saldos = await _balance(c)
    assert saldos["5135"] == 1000 and saldos["2205"] == -1000


async def test_catalogo_duplicado_y_costo_protegido(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    tercero = {"nombre": "Cliente", "tipo": "cliente", "numero_documento": "555"}
    assert (await c.post("/api/configuracion/terceros", json=tercero)).status_code == 201
    r = await c.post("/api/configuracion/terceros", json=tercero)
    assert r.status_code == 409 and "Ya existe" in r.json()["detail"]

    prod = (await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "Gorra", "sku": "G-1", "costo_promedio_ponderado": 999})).json()
    assert "costo_promedio_ponderado" not in prod
    r = await c.put(f"/api/inventario/catalogo-productos/{prod['id']}", json={"costo_promedio_ponderado": 5})
    assert "costo_promedio_ponderado" not in r.json()
