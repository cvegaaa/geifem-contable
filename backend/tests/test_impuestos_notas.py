"""Notas con retenciones prorrateadas, impuesto al consumo, saldos iniciales y reportes fiscales."""
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


async def _conceptos(c) -> dict:
    return {x["nombre"]: x["id"] for x in (await c.get("/api/configuracion/conceptos-retencion")).json()}


async def _venta(c, cliente_extra=None, **producto):
    prod = (await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "Servicio", "sku": "S-1", "inventariable": False, **producto})).json()
    cliente = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Cliente", "tipo": "cliente", "numero_documento": "1001", **(cliente_extra or {})})).json()
    resol = (await c.post("/api/configuracion/resoluciones-dian", json={
        "numero_resolucion": "1876", "prefijo": "FE", "rango_desde": 1, "rango_hasta": 100,
        "fecha_inicio": "2026-01-01", "fecha_fin": "2027-12-31"})).json()
    return prod, cliente, resol


def _factura(prod, cliente, resol, valor=1_000_000):
    return {"cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
            "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": valor, "tarifa_iva": 19}]}


async def test_nota_credito_prorratea_retenciones(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    conceptos = await _conceptos(c)
    prod, cliente, resol = await _venta(
        c, {"agente_retenedor": True, "agente_reteiva": True},
        concepto_retefuente_venta_id=conceptos["Servicios generales (declarante)"])
    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["retenciones"]["retefuente"] == 40000 and fac["retenciones"]["reteiva"] == 28500
    assert fac["saldo_pendiente"] == 1_190_000 - 68_500

    # Nota crédito por la mitad: revierte la mitad de la venta y de las retenciones.
    r = await c.post("/api/facturacion/notas-credito-debito", json={
        "factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Devolución parcial",
        "items": [{"descripcion": "Devolución", "precio_unitario": 500_000, "tarifa_iva": 19}]})
    assert r.status_code == 201, r.text
    nc = r.json()
    assert nc["proporcion"] == 0.5
    assert nc["retenciones"]["retefuente"] == 20000 and nc["retenciones"]["reteiva"] == 14250
    assert nc["neto"] == 595_000 - 34_250
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 1_121_500 - 560_750

    saldos = await _balance(c)
    assert saldos["1355"] == 34_250          # la mitad de las retenciones a favor
    assert saldos["1305"] == 560_750
    assert saldos["4175"] == 500_000 and saldos["4135"] == -1_000_000

    # Anular la nota deja todo como estaba.
    assert (await c.post(f"/api/facturacion/notas-credito-debito/{nc['id']}/anular", json={})).status_code == 200
    saldos = await _balance(c)
    assert saldos["1355"] == 68_500 and "4175" not in saldos
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 1_121_500


async def test_impuesto_al_consumo_en_la_venta(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    # Sin cuenta contable el impuesto no se puede crear.
    r = await c.post("/api/configuracion/impuestos", json={"nombre": "INC restaurantes", "tarifa": 8})
    assert r.status_code == 422 and "cuenta" in r.json()["detail"].lower()
    r = await c.post("/api/configuracion/impuestos", json={
        "nombre": "INC restaurantes 8%", "tarifa": 8, "cuenta_contable": "2495"})
    assert r.status_code == 201, r.text
    inc_id = r.json()["id"]

    prod, cliente, resol = await _venta(c, impuesto_consumo_id=inc_id, tipo_iva="excluido")
    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["iva_total"] == 0 and fac["inc_total"] == 80_000 and fac["total"] == 1_080_000
    saldos = await _balance(c)
    assert saldos["1305"] == 1_080_000 and saldos["4135"] == -1_000_000 and saldos["2495"] == -80_000

    # El INC también se revierte con una nota crédito total.
    nc = (await c.post("/api/facturacion/notas-credito-debito", json={
        "factura_id": fac["id"], "tipo": "credito", "fecha": FECHA, "motivo": "Anulación",
        "items": [{"descripcion": "Devolución total", "precio_unitario": 1_000_000}]})).json()
    assert nc["inc_total"] == 80_000 and nc["total"] == 1_080_000
    saldos = await _balance(c)
    assert saldos["2495"] == 0 and saldos["1305"] == 0

    # Un impuesto inexistente no se acepta en el producto.
    r = await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "X", "sku": "X", "impuesto_consumo_id": "0123456789abcdef01234567"})
    assert r.status_code == 422


async def test_concepto_con_cuentas_propias(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await c.post("/api/configuracion/plan-cuentas", json={
        "codigo": "236540", "nombre": "Retención compras", "naturaleza": "credito", "acepta_movimientos": True})
    conceptos = await _conceptos(c)
    cid = conceptos["Compras generales (declarante)"]
    r = await c.put(f"/api/configuracion/conceptos-retencion/{cid}", json={
        "tipo": "retefuente", "nombre": "Compras generales (declarante)", "tarifa": 2.5, "base_uvt": 27,
        "cuenta_pasivo": "236540"})
    assert r.status_code == 200, r.text
    r = await c.put(f"/api/configuracion/conceptos-retencion/{cid}", json={
        "tipo": "retefuente", "nombre": "Compras generales (declarante)", "tarifa": 2.5, "cuenta_pasivo": "999999"})
    assert r.status_code == 422

    prov = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor", "tipo": "proveedor", "numero_documento": "2002"})).json()
    fp = await c.post("/api/compras/facturas-proveedor", json={
        "proveedor_id": prov["id"], "numero_factura": "A-1", "fecha": FECHA, "afecta_inventario": False,
        "items": [{"descripcion": "Compra", "cantidad": 1, "costo_unitario": 10_000_000, "tarifa_iva": 19,
                   "concepto_retefuente_id": cid}]})
    assert fp.status_code == 201, fp.text
    saldos = await _balance(c)
    assert saldos["236540"] == -250_000 and "2365" not in saldos     # va a la cuenta del concepto


async def test_saldo_inicial_de_caja_y_banco_se_contabiliza(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await c.post("/api/configuracion/plan-cuentas", json={
        "codigo": "111005", "nombre": "Bancolombia ahorros", "naturaleza": "debito", "acepta_movimientos": True})
    r = await c.post("/api/tesoreria/cuentas-bancarias", json={
        "nombre": "Bancolombia", "cuenta_contable": "111005", "saldo_inicial": 5_000_000})
    assert r.status_code == 201, r.text
    banco = r.json()
    saldos = await _balance(c)
    assert saldos["111005"] == 5_000_000 and saldos["3105"] == -5_000_000      # debe estar en el libro
    assert (await c.get("/api/tesoreria/bancos")).json()[0]["saldo"] == 5_000_000

    # Editar el saldo inicial regenera el asiento; no se duplica.
    r = await c.put(f"/api/tesoreria/cuentas-bancarias/{banco['id']}", json={
        "nombre": "Bancolombia", "cuenta_contable": "111005", "saldo_inicial": 3_000_000})
    assert r.status_code == 200, r.text
    assert (await _balance(c))["111005"] == 3_000_000

    # Con movimientos no se puede cambiar la cuenta contable.
    await c.post("/api/tesoreria/movimientos", json={
        "cuenta_tipo": "banco", "cuenta_id": banco["id"], "tipo": "egreso", "fecha": FECHA, "valor": 100,
        "concepto": "Gasto", "cuenta_contrapartida": "5195"})
    r = await c.put(f"/api/tesoreria/cuentas-bancarias/{banco['id']}", json={
        "nombre": "Bancolombia", "cuenta_contable": "1110", "saldo_inicial": 3_000_000})
    assert r.status_code == 409
    assert (await c.get("/api/tesoreria/bancos")).json()[0]["saldo"] == 2_999_900


async def test_reportes_fiscales_incluyen_retenciones_sufridas_y_autorretencion(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    r = await c.get("/api/configuracion/datos-empresa")
    emp = r.json()[0]
    await c.put(f"/api/configuracion/datos-empresa/{emp['id']}", json={
        "nit": emp["nit"], "razon_social": emp["razon_social"], "autorretenedor_renta": True,
        "tarifa_autorretencion": 0.8})
    prod, cliente, resol = await _venta(c, {"agente_reteiva": True})
    await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))

    rep = (await c.get("/api/reportes/fiscales/impuestos-y-retenciones", params=RANGO)).json()
    assert rep["resumen"]["autorretenciones"] == 8_000
    assert rep["resumen"]["retenciones_que_te_practicaron"] == 28_500
    impuestos = {f["impuesto"] for f in rep["filas"]}
    assert {"Autorretención de renta", "ReteIVA que te practicaron"} <= impuestos

    f350 = (await c.get("/api/reportes/fiscales/formulario-350", params=RANGO)).json()
    assert f350["resumen"]["autorretencion"] == 8_000

    ex = (await c.get("/api/reportes/exogena/formato-1003", params=RANGO)).json()
    assert ex["resumen"]["retencion"] == 28_500


async def test_completar_plan_de_cuentas(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    cuentas = (await c.get("/api/configuracion/plan-cuentas")).json()
    quitar = next(x for x in cuentas if x["codigo"] == "2515")
    await c.post(f"/api/configuracion/plan-cuentas/{quitar['id']}/inactivar")
    r = await c.post("/api/configuracion/plan-cuentas/cargar-sugeridas")
    assert r.status_code == 200 and r.json()["agregadas"] == 0     # la inactiva existe: no se duplica
