"""Motor de impuestos: el perfil de la empresa y del tercero decide qué se aplica."""
from tests.conftest import registrar

FECHA = "2026-10-01"
RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


async def _empresa(nuevo_cliente, **perfil):
    c = nuevo_cliente()
    data = await registrar(c, "dueno@a.co", "900111222")
    if perfil:
        emp = (await c.get(f"/api/configuracion/datos-empresa/{data['empresa_activa_id']}")).json()
        base = {k: emp[k] for k in ("nit", "razon_social", "regimen_tributario", "responsable_iva") if k in emp}
        r = await c.put(f"/api/configuracion/datos-empresa/{data['empresa_activa_id']}", json={**base, **perfil})
        assert r.status_code == 200, r.text
    return c


async def _conceptos(c) -> dict:
    return {x["nombre"]: x["id"] for x in (await c.get("/api/configuracion/conceptos-retencion")).json()}


async def _balance(c) -> dict:
    r = await c.get("/api/reportes/contables/balance-de-prueba", params=RANGO)
    return {f["codigo"]: f["saldo"] for f in r.json()["filas"]}


async def _base_venta(c, cliente_extra=None, **producto):
    prod = (await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "Servicio técnico", "sku": "SRV-1", "inventariable": False, **producto})).json()
    cliente = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Cliente", "tipo": "cliente", "numero_documento": "1001", **(cliente_extra or {})})).json()
    resol = (await c.post("/api/configuracion/resoluciones-dian", json={
        "numero_resolucion": "1876", "prefijo": "FE", "rango_desde": 1, "rango_hasta": 100,
        "fecha_inicio": "2026-01-01", "fecha_fin": "2027-12-31"})).json()
    return prod, cliente, resol


def _factura(prod, cliente, resol, valor=1_000_000, tarifa_iva=19):
    return {"cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
            "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": valor, "tarifa_iva": tarifa_iva}]}


async def test_empresa_nueva_trae_conceptos_y_perfil(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    conceptos = await _conceptos(c)
    assert "Compras generales (declarante)" in conceptos and "ReteIVA general (15% del IVA)" in conceptos
    cap = (await c.get("/api/configuracion/perfil-tributario")).json()
    assert cap["practica_retefuente"] and cap["sufre_retefuente"] and cap["cobra_iva"]


async def test_simple_no_retiene_ni_sufre_retefuente_pero_si_reteiva(nuevo_cliente):
    c = await _empresa(nuevo_cliente, regimen_tributario="SIMPLE")
    cap = (await c.get("/api/configuracion/perfil-tributario")).json()
    assert not cap["sufre_retefuente"] and not cap["practica_retefuente"]
    assert cap["sufre_reteiva"] and any("911" in n for n in cap["notas"])

    # La interfaz no ofrece estas opciones; el servidor tampoco las acepta.
    conceptos = await _conceptos(c)
    r = await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "X", "sku": "X", "concepto_retefuente_venta_id": conceptos["Servicios generales (declarante)"]})
    assert r.status_code == 422 and "SIMPLE" in r.json()["detail"]
    r = await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "X", "sku": "X", "concepto_retefuente_compra_id": conceptos["Servicios generales (declarante)"]})
    assert r.status_code == 422

    # Un cliente agente retenedor no le retiene renta, pero sí ReteIVA.
    prod, cliente, resol = await _base_venta(c, {"agente_retenedor": True, "agente_reteiva": True})
    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["retenciones"]["retefuente"] == 0
    assert fac["retenciones"]["reteiva"] == 28500  # 15% de 190.000
    assert fac["total_a_cobrar"] == 1_190_000 - 28_500


async def test_simple_no_practica_retefuente_en_compras(nuevo_cliente):
    c = await _empresa(nuevo_cliente, regimen_tributario="SIMPLE")
    conceptos = await _conceptos(c)
    proveedor = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor", "tipo": "proveedor", "numero_documento": "2002"})).json()
    r = await c.post("/api/compras/facturas-proveedor/previsualizar", json={
        "proveedor_id": proveedor["id"], "numero_factura": "A-1", "fecha": FECHA, "afecta_inventario": False,
        "items": [{"descripcion": "Servicio", "cantidad": 1, "costo_unitario": 1_000_000,
                   "concepto_retefuente_id": conceptos["Servicios generales (declarante)"]}]})
    assert r.status_code == 200, r.text
    assert r.json()["retenciones"]["retefuente"] == 0


async def test_ordinaria_practica_retenciones_a_proveedores(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    conceptos = await _conceptos(c)
    declarante = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor A", "tipo": "proveedor", "numero_documento": "2002"})).json()
    no_declarante = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor B", "tipo": "proveedor", "numero_documento": "2003", "declarante_renta": False})).json()
    simple = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor SIMPLE", "tipo": "proveedor", "numero_documento": "2004", "regimen": "SIMPLE"})).json()

    def cuerpo(prov, numero, valor=1_000_000):
        return {"proveedor_id": prov["id"], "numero_factura": numero, "fecha": FECHA, "afecta_inventario": False,
                "concepto_reteica_id": conceptos["ReteICA (ajusta la tarifa a tu municipio y actividad)"],
                "items": [{"descripcion": "Servicio", "cantidad": 1, "costo_unitario": valor, "tarifa_iva": 19,
                           "concepto_retefuente_id": conceptos["Servicios generales (declarante)"]}]}

    r = (await c.post("/api/compras/facturas-proveedor", json=cuerpo(declarante, "F-1"))).json()
    assert r["retenciones"] == {"retefuente": 40000.0, "reteica": 4140.0, "reteiva": 28500.0}
    assert r["total_a_pagar"] == 1_190_000 - 40_000 - 4_140 - 28_500

    r = (await c.post("/api/compras/facturas-proveedor", json=cuerpo(no_declarante, "F-2"))).json()
    assert r["retenciones"]["retefuente"] == 60000.0   # 6% a no declarantes

    r = (await c.post("/api/compras/facturas-proveedor", json=cuerpo(simple, "F-3"))).json()
    assert r["retenciones"]["retefuente"] == 0 and r["retenciones"]["reteica"] == 0   # art. 911 ET
    assert r["retenciones"]["reteiva"] == 28500                                       # el IVA sí

    # Bajo la cuantía mínima (4 UVT = 209.496) no se retiene.
    r = (await c.post("/api/compras/facturas-proveedor", json=cuerpo(declarante, "F-4", valor=100_000))).json()
    assert r["retenciones"]["retefuente"] == 0
    assert any("cuantía mínima" in (d["motivo"] or "") for d in r["detalle_retenciones"])


async def test_retencion_sufrida_en_ventas_y_cobro_neto(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    conceptos = await _conceptos(c)
    prod, cliente, resol = await _base_venta(
        c, {"agente_retenedor": True},
        concepto_retefuente_venta_id=conceptos["Servicios generales (declarante)"])

    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["retenciones"]["retefuente"] == 40000.0
    assert fac["saldo_pendiente"] == 1_190_000 - 40_000
    saldos = await _balance(c)
    assert saldos["1305"] == 1_150_000
    assert saldos["1355"] == 40_000          # retención a favor
    assert saldos["4135"] == -1_000_000 and saldos["2408"] == -190_000

    # El cliente paga el neto y la factura queda saldada.
    caja = (await c.get("/api/tesoreria/caja")).json()[0]
    r = await c.post("/api/tesoreria/pagos", json={
        "documento_tipo": "cxc", "documento_id": fac["id"], "cuenta_tipo": "caja", "cuenta_id": caja["id"],
        "fecha": FECHA, "valor": 1_150_000})
    assert r.status_code == 201, r.text
    assert (await c.get(f"/api/facturacion/facturas/{fac['id']}")).json()["saldo_pendiente"] == 0


async def test_autorretenedor_y_no_responsable_de_iva(nuevo_cliente):
    c = await _empresa(nuevo_cliente, autorretenedor_renta=True, tarifa_autorretencion=0.8)
    conceptos = await _conceptos(c)
    cap = (await c.get("/api/configuracion/perfil-tributario")).json()
    assert not cap["sufre_retefuente"] and cap["autorretenedor_renta"]

    prod, cliente, resol = await _base_venta(c, {"agente_retenedor": True})
    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["retenciones"]["retefuente"] == 0 and fac["autorretencion"] == 8000.0
    saldos = await _balance(c)
    assert saldos["1355"] == 8000 and saldos["2365"] == -8000    # débito anticipo / crédito por pagar

    r = await c.post("/api/inventario/catalogo-productos", json={
        "nombre": "Y", "sku": "Y", "concepto_retefuente_venta_id": conceptos["Compras generales (declarante)"]})
    assert r.status_code == 422


async def test_no_responsable_de_iva(nuevo_cliente):
    c = await _empresa(nuevo_cliente, responsable_iva=False)
    r = await c.post("/api/inventario/catalogo-productos", json={"nombre": "Z", "sku": "Z", "tarifa_iva": 19})
    assert r.status_code == 422 and "responsable de IVA" in r.json()["detail"]

    prod, cliente, resol = await _base_venta(c)
    fac = (await c.post("/api/facturacion/facturas", json=_factura(prod, cliente, resol))).json()
    assert fac["iva_total"] == 0 and fac["total"] == 1_000_000      # aunque se envíe 19%

    proveedor = (await c.post("/api/configuracion/terceros", json={
        "nombre": "Proveedor", "tipo": "proveedor", "numero_documento": "2002"})).json()
    fp = (await c.post("/api/compras/facturas-proveedor", json={
        "proveedor_id": proveedor["id"], "numero_factura": "A-9", "fecha": FECHA, "afecta_inventario": False,
        "cuenta_gasto": "5135",
        "items": [{"descripcion": "Servicio", "cantidad": 1, "costo_unitario": 1000, "tarifa_iva": 19}]})).json()
    assert fp["iva_total"] == 0 and fp["total"] == 1190    # el IVA pagado sube el gasto
    saldos = await _balance(c)
    assert saldos["5135"] == 1190 and "2408" not in saldos


async def test_perfil_valida_reglas_legales(nuevo_cliente):
    c = nuevo_cliente()
    base = {"nombre": "X", "email": "x@a.co", "password": "clave-segura-1"}
    r = await c.post("/api/auth/registro", json={**base, "empresa": {
        "nit": "900111222", "razon_social": "Empresa SAS", "regimen_tributario": "SIMPLE", "agente_retenedor": True}})
    assert r.status_code == 422 and "911" in str(r.json())
    r = await c.post("/api/auth/registro", json={**base, "empresa": {
        "nit": "900111222", "razon_social": "Empresa SAS", "regimen_tributario": "SIMPLE",
        "autorretenedor_renta": True}})
    assert r.status_code == 422
