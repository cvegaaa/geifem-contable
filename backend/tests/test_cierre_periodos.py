"""Cierre de periodos: ningún módulo puede mover lo ya cerrado."""
from core.dinero import centavos, redondear
from tests.conftest import registrar

RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


async def _empresa(nuevo_cliente):
    c = nuevo_cliente()
    await registrar(c, "dueno@a.co", "900111222")
    cuentas = {x["codigo"]: x["id"] for x in (await c.get("/api/configuracion/plan-cuentas")).json()}
    return c, cuentas


def _comprobante(cuentas, fecha, valor=1000, estado="contabilizado"):
    return {"tipo": "ajuste", "fecha": fecha, "estado": estado,
            "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": valor},
                       {"cuenta_puc_id": cuentas["3105"], "credito": valor}]}


async def test_periodo_cerrado_bloquea_crear_editar_y_anular(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    viejo = (await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, "2026-08-10"))).json()
    reciente = (await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, "2026-09-05"))).json()

    r = await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-08-31"})
    assert r.status_code == 200 and r.json()["fecha_cierre"] == "2026-08-31"

    # Crear en el periodo cerrado
    r = await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, "2026-08-31"))
    assert r.status_code == 409 and "cerrado" in r.json()["detail"]
    # Editar y anular lo que ya estaba dentro del periodo
    assert (await c.put(f"/api/contabilidad/comprobantes/{viejo['id']}", json=_comprobante(cuentas, "2026-08-10", 5))).status_code == 409
    assert (await c.post(f"/api/contabilidad/comprobantes/{viejo['id']}/anular", json={})).status_code == 409
    # No se puede "escapar" moviendo la fecha de un documento abierto hacia el periodo cerrado
    assert (await c.put(f"/api/contabilidad/comprobantes/{reciente['id']}", json=_comprobante(cuentas, "2026-08-20"))).status_code == 409
    # Lo posterior al cierre sigue funcionando
    assert (await c.put(f"/api/contabilidad/comprobantes/{reciente['id']}", json=_comprobante(cuentas, "2026-09-05", 7))).status_code == 200


async def test_cierre_protege_a_todos_los_modulos(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod = (await c.post("/api/inventario/catalogo-productos", json={"nombre": "X", "sku": "X"})).json()
    bodega = (await c.get("/api/inventario/bodegas")).json()[0]
    ent = (await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": "2026-07-15",
        "items": [{"producto_id": prod["id"], "cantidad": 5, "costo_unitario": 100}]})).json()
    await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-07-31"})

    assert (await c.post(f"/api/compras/recepcion-mercancia/{ent['id']}/anular", json={})).status_code == 409
    r = await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": "2026-07-20",
        "items": [{"producto_id": prod["id"], "cantidad": 1, "costo_unitario": 100}]})
    assert r.status_code == 409
    r = await c.post("/api/tesoreria/cuentas-bancarias", json={"nombre": "Banco", "saldo_inicial": 0})
    assert r.status_code == 201


async def test_reglas_del_cierre(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    # Solo fines de mes, y solo periodos ya terminados.
    assert (await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-08-15"})).status_code == 422
    assert (await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2099-12-31"})).status_code == 422
    # Con borradores dentro del periodo no se puede cerrar.
    borrador = (await c.post("/api/contabilidad/comprobantes", json=_comprobante(cuentas, "2026-08-12", estado="borrador"))).json()
    r = await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-08-31"})
    assert r.status_code == 409 and "borrador" in r.json()["detail"]
    await c.post(f"/api/contabilidad/comprobantes/{borrador['id']}/anular", json={})
    assert (await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-08-31"})).status_code == 200

    # Reabrir exige administrador y motivo; queda constancia.
    await c.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Contador", "email": "cont@a.co", "password": "clave-segura-1", "rol": "contador"})
    cont = nuevo_cliente()
    await cont.post("/api/auth/login", json={"email": "cont@a.co", "password": "clave-segura-1"})
    cont.headers["X-Empresa-Id"] = c.headers["X-Empresa-Id"]
    assert (await cont.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-07-31", "motivo": "x"})).status_code == 403
    assert (await c.put("/api/contabilidad/cierre", json={"fecha_cierre": None})).status_code == 422   # sin motivo
    r = await c.put("/api/contabilidad/cierre", json={"fecha_cierre": None, "motivo": "Corrección autorizada"})
    assert r.status_code == 200 and r.json()["fecha_cierre"] is None
    acciones = [h["accion"] for h in r.json()["historial"]]
    assert acciones[:2] == ["reabierto", "cerrado"]


def test_redondeo_contable_y_centavos():
    assert round(2.675, 2) == 2.67            # el redondeo de Python se equivoca con binarios
    assert redondear(2.675) == 2.68           # el contable no
    assert redondear(1.005) == 1.01 and redondear(2.5, 0) == 3 and redondear(1234567, -3) == 1235000
    assert centavos(0.1) + centavos(0.2) == centavos(0.3)     # 0.1 + 0.2 != 0.3 en float
    assert sum(centavos(0.1) for _ in range(10)) == 100
