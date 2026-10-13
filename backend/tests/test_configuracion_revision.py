"""Revisión de Configuración: cuentas por producto y empleado, INC único, resoluciones DIAN y plan a 6 dígitos."""
from core.dian.cliente_pt import ClientePTNoConfigurado
from tests.test_documentos import FECHA, _empresa


async def test_plan_de_cuentas_incluye_auxiliares_de_seis_digitos(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    plan = (await c.get("/api/configuracion/plan-cuentas")).json()
    seis = [x for x in plan if len(x["codigo"]) == 6]
    assert len(seis) > 50 and all(x["nivel"] == 4 and x["acepta_movimientos"] for x in seis)
    por_codigo = {x["codigo"]: x for x in plan}
    assert por_codigo["110505"]["nombre"] == "Caja general" and por_codigo["110505"]["codigo_padre"] == "1105"
    assert por_codigo["413505"]["codigo_padre"] == "4135"


async def test_producto_nace_con_las_cuentas_de_la_empresa_y_permite_otras(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    p = (await c.post("/api/inventario/catalogo-productos", json={"nombre": "Camisa", "sku": "C-1"})).json()
    assert (p["cuenta_ingreso"], p["cuenta_inventario"], p["cuenta_costo"]) == ("4135", "1435", "6135")
    # Un servicio solo lleva cuenta de ingreso; otro producto puede ir a un ingreso distinto (auxiliar de 6 dígitos).
    s = (await c.post("/api/inventario/catalogo-productos", json={"nombre": "Asesoría", "sku": "S-1", "inventariable": False})).json()
    assert s["cuenta_ingreso"] == "4135" and not s.get("cuenta_inventario") and not s.get("cuenta_costo")
    o = (await c.post("/api/inventario/catalogo-productos", json={"nombre": "Servicio", "sku": "S-2", "cuenta_ingreso": "413510"})).json()
    assert o["cuenta_ingreso"] == "413510"
    assert (await c.post("/api/inventario/catalogo-productos", json={"nombre": "X", "sku": "X-1", "cuenta_ingreso": "999999"})).status_code == 422


async def test_empleado_nace_con_sus_cuentas_y_la_nomina_las_usa(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    base = {"primer_nombre": "Ana", "primer_apellido": "Ruiz", "numero_documento": "100", "fecha_ingreso": "2026-01-01",
            "salario_basico": 2_000_000, "tipo_contrato": "indefinido", "frecuencia_pago": "mensual", "riesgo_arl": "I"}
    ana = (await c.post("/api/nomina/empleados", json=base)).json()
    assert ana["cuenta_gasto_salarios"] == "5105" and ana["cuenta_gasto_prestaciones"] == "5105"
    ventas = (await c.post("/api/nomina/empleados", json={**base, "numero_documento": "200", "primer_nombre": "Luis",
                                                          **{k: "5205" for k in ("cuenta_gasto_salarios", "cuenta_gasto_horas_extra", "cuenta_gasto_aux_transporte",
                                                                                              "cuenta_gasto_seguridad_social", "cuenta_gasto_parafiscales", "cuenta_gasto_prestaciones")}}))
    assert ventas.status_code == 201, ventas.text
    assert (await c.post("/api/nomina/empleados", json={**base, "numero_documento": "300", "cuenta_gasto_salarios": "123456"})).status_code == 422

    per = await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 3, "tipo": "mensual", "fecha_pago": "2026-03-31"})
    assert per.status_code == 201, per.text
    bal = (await c.get("/api/reportes/contables/balance-de-prueba", params={"desde": "2026-01-01", "hasta": "2026-12-31"})).json()
    saldos = {f["codigo"]: f["saldo"] for f in bal["filas"]}
    assert saldos["5105"] > 0 and saldos["5205"] > 0          # el gasto de cada empleado va a sus cuentas
    assert abs(saldos["5105"] - saldos["5205"]) < 1             # mismo salario, mismo gasto


async def test_impuesto_al_consumo_unico_con_varias_tarifas(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    assert (await c.get("/api/configuracion/impuesto-consumo/cuenta")).json() == {"cuenta_contable": "2495"}
    a = (await c.post("/api/configuracion/impuestos", json={"nombre": "Restaurantes 8 %", "tarifa": 8})).json()
    b = (await c.post("/api/configuracion/impuestos", json={"nombre": "Telefonía 4 %", "tarifa": 4})).json()
    assert a["cuenta_contable"] == b["cuenta_contable"] == "2495"
    # Cambiar la cuenta única cambia todas las tarifas.
    r = await c.put("/api/configuracion/impuesto-consumo/cuenta", json={"cuenta_contable": "249505"})
    assert r.status_code == 200
    assert {t["cuenta_contable"] for t in (await c.get("/api/configuracion/impuestos")).json()} == {"249505"}
    assert (await c.put("/api/configuracion/impuesto-consumo/cuenta", json={"cuenta_contable": "000000"})).status_code == 422


async def test_resoluciones_listas_para_sincronizar_con_la_dian(nuevo_cliente, monkeypatch):
    c, _ = await _empresa(nuevo_cliente)
    # Sin proveedor tecnológico conectado, el servicio responde con un mensaje claro.
    r = await c.post("/api/configuracion/resoluciones-dian/sincronizar")
    assert r.status_code == 501 and "proveedor tecnológico" in r.json()["detail"]

    class Falso(ClientePTNoConfigurado):
        async def listar_resoluciones(self, empresa_id):
            return [{"NumeroResolucion": "18760000099", "FechaResolucion": "2026-01-02", "Prefijo": "SETP", "DesdeNumero": 990000000,
                     "HastaNumero": 995000000, "FechaDesde": "2026-01-02", "FechaHasta": "2027-01-02", "ClaveTecnica": "abc", "TipoDocumento": "01"}]

    monkeypatch.setattr("core.dian.cliente_pt.get_cliente_pt", lambda: Falso())
    r = await c.post("/api/configuracion/resoluciones-dian/sincronizar")
    assert r.status_code == 200 and r.json() == {"creadas": 1, "actualizadas": 0}
    r = await c.post("/api/configuracion/resoluciones-dian/sincronizar")
    assert r.json() == {"creadas": 0, "actualizadas": 1}
    res = (await c.get("/api/configuracion/resoluciones-dian")).json()
    assert len(res) == 1 and res[0]["origen"] == "dian" and res[0]["clave_tecnica"] == "abc" and res[0]["consecutivo_actual"] == 989999999
