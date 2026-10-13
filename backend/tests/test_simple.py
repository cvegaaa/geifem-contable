"""Formularios SIMPLE: anticipo bimestral (2593) y declaración anual (260)."""
from tests.conftest import registrar
from tests.test_documentos import _comprobante

RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


async def _empresa_simple(nuevo_cliente):
    c = nuevo_cliente()
    await registrar(c, "dueno@a.co", "900111222")
    emp = (await c.get("/api/configuracion/datos-empresa")).json()[0]
    cuerpo = {"nit": emp["nit"], "razon_social": emp["razon_social"], "regimen_tributario": "SIMPLE",
              "agente_retenedor": False, "agente_reteiva": False, "grupo_simple": 2}
    r = await c.put(f"/api/configuracion/datos-empresa/{emp['id']}", json=cuerpo)
    assert r.status_code == 200, r.text
    cuentas = {x["codigo"]: x["id"] for x in (await c.get("/api/configuracion/plan-cuentas")).json()}
    return c, cuentas


async def _ingreso(c, cuentas, fecha, valor):
    r = await c.post("/api/contabilidad/comprobantes", json={
        "tipo": "ajuste", "fecha": fecha, "estado": "contabilizado", "descripcion": "Ingreso",
        "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": valor}, {"cuenta_puc_id": cuentas["4135"], "credito": valor}]})
    assert r.status_code == 201, r.text


async def test_formulario_2593_aplica_tarifa_del_tramo(nuevo_cliente):
    c, cuentas = await _empresa_simple(nuevo_cliente)
    await _ingreso(c, cuentas, "2026-01-15", 10_000_000)
    await _ingreso(c, cuentas, "2026-02-10", 5_000_000)
    r = await c.get("/api/reportes/fiscales/form-2593-simple", params={"desde": "2026-01-01", "hasta": "2026-02-28"})
    assert r.status_code == 200, r.text
    res = r.json()["resumen"]
    # 15 millones << 6.000 UVT: tramo de la tarifa más baja del grupo 2 (1,6 %).
    assert res["ingresos_bimestre"] == 15_000_000 and res["tarifa"] == 1.6
    assert res["anticipo"] == 240_000 and res["valor_a_pagar"] == 240_000
    assert "verificadas" in res["advertencia"]


async def test_formulario_260_descuenta_anticipos_y_tarifas_editables(nuevo_cliente):
    c, cuentas = await _empresa_simple(nuevo_cliente)
    await _ingreso(c, cuentas, "2026-01-15", 10_000_000)
    await _ingreso(c, cuentas, "2026-03-15", 20_000_000)
    t = (await c.get("/api/configuracion/tarifas-simple")).json()
    t["grupos"]["2"]["tramos"][0]["tarifa"] = 2.0
    t["verificado"] = True
    assert (await c.put("/api/configuracion/tarifas-simple", json=t)).status_code == 200
    bad = {"verificado": True, "grupos": {"2": {"tramos": [{"hasta_uvt": 100, "tarifa": 1}, {"hasta_uvt": 50, "tarifa": 2}]}}}
    assert (await c.put("/api/configuracion/tarifas-simple", json=bad)).status_code == 422

    r = await c.get("/api/reportes/fiscales/form-260-simple", params=RANGO)
    assert r.status_code == 200, r.text
    res = r.json()["resumen"]
    assert res["ingresos_brutos_anuales"] == 30_000_000 and res["tarifa_anual"] == 2.0
    assert res["impuesto_consolidado"] == 600_000 and res["anticipos_bimestrales"] == 600_000
    assert res["saldo_a_pagar"] == 0 and res.get("advertencia") is None
