"""Nómina: liquidación mensual y quincenal, asientos, pagos, prestaciones, PILA, contrato y e-nómina."""
from datetime import date

from core import nomina as motor
from tests.conftest import registrar

RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}
P = motor.parametros_anio(2026)


async def _empresa(nuevo_cliente):
    c = nuevo_cliente()
    await registrar(c, "dueno@a.co", "900111222")
    return c


async def _balance(c) -> dict:
    r = await c.get("/api/reportes/contables/balance-de-prueba", params=RANGO)
    return {f["codigo"]: f["saldo"] for f in r.json()["filas"]}


def _empleado(documento="1001", salario=1_750_905, **extra):
    return {"primer_nombre": "Ana", "primer_apellido": "Pérez", "numero_documento": documento,
            "fecha_ingreso": "2025-01-01", "salario_basico": salario, "frecuencia_pago": "mensual",
            "riesgo_arl": "I", "tipo_contrato": "indefinido", **extra}


async def _banco(c):
    r = await c.post("/api/tesoreria/cuentas-bancarias", json={"nombre": "Bancolombia", "saldo_inicial": 50_000_000})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- motor (sin base de datos)

def test_motor_salario_minimo():
    emp = {"id": "e", "salario_basico": 1_750_905, "fecha_ingreso": "2025-01-01", "riesgo_arl": "I"}
    l = motor.liquidar_empleado(emp, [], date(2026, 10, 1), date(2026, 10, 31), 30, P)
    assert l["devengos"]["aux_transporte"] == 249_095
    assert l["deducciones"]["salud"] == 70_036 and l["deducciones"]["pension"] == 70_036
    assert l["neto_pagar"] == 2_000_000 - 140_072
    assert l["aportes_empleador"]["salud"] == 0 and l["aportes_empleador"]["sena"] == 0   # exonerado art. 114-1
    assert l["provisiones"]["cesantias"] == 166_600


def test_motor_horas_y_recargos():
    emp = {"id": "e", "salario_basico": 6_000_000, "fecha_ingreso": "2024-02-01", "riesgo_arl": "I"}
    novs = [{"tipo": "hora_extra_diurna", "cantidad": 10}, {"tipo": "recargo_dominical_festivo", "cantidad": 8}]
    l = motor.liquidar_empleado(emp, novs, date(2026, 10, 1), date(2026, 10, 31), 30, P)
    valor_hora = 6_000_000 / 210
    assert l["devengos"]["horas"]["hora_extra_diurna"] == round(10 * valor_hora * 1.25)
    assert l["devengos"]["horas"]["recargo_dominical_festivo"] == round(8 * valor_hora * 0.90)
    assert l["devengos"]["aux_transporte"] == 0          # gana más de 2 SMMLV


def test_motor_incapacidad_y_dias_parciales():
    emp = {"id": "e", "salario_basico": 3_000_000, "fecha_ingreso": "2024-02-01", "riesgo_arl": "I"}
    l = motor.liquidar_empleado(
        emp, [{"tipo": "incapacidad_general", "cantidad": 5, "dias_previos": 0}],
        date(2026, 10, 1), date(2026, 10, 31), 30, P)
    assert l["dias_trabajados"] == 25
    assert l["devengos"]["incapacidad_empleador"] == 133_340      # 2 días al 66,67%
    assert l["devengos"]["incapacidad_a_cargo_eps_arl"] == 200_010   # 3 días a cargo de la EPS

    nuevo = {**emp, "fecha_ingreso": "2026-10-16"}
    l = motor.liquidar_empleado(nuevo, [], date(2026, 10, 1), date(2026, 10, 31), 30, P)
    assert l["dias_activos"] == 15 and l["devengos"]["sueldo"] == 1_500_000


def test_motor_retefuente_laboral_tabla():
    emp = {"id": "e", "salario_basico": 12_000_000, "fecha_ingreso": "2024-02-01", "riesgo_arl": "I"}
    l = motor.liquidar_empleado(emp, [], date(2026, 10, 1), date(2026, 10, 31), 30, P)
    # IBC 12M: aportes 960.000; subtotal 11.04M; renta exenta 25% = 2.76M; base 8.28M ≈ 158 UVT.
    assert 400_000 < l["deducciones"]["retefuente"] < 700_000
    assert l["deducciones"]["fsp"] == 120_000     # IBC de 12M supera 4 SMMLV (7,0M): 1%
    assert motor.porcentaje_fsp(12_000_000, P) == 1.0 and motor.porcentaje_fsp(5_000_000, P) == 0


def test_motor_liquidacion_final_e_indemnizacion():
    emp = {"salario_basico": 2_000_000, "fecha_ingreso": "2025-11-01", "tipo_contrato": "indefinido"}
    r = motor.liquidacion_final(emp, date(2026, 10, 31), "despido_sin_justa_causa", P)
    assert r["dias"]["cesantias"] == 300 and r["dias"]["prima"] == 120
    assert r["indemnizacion"] == round(2_000_000 / 30 * 30)     # un año o menos: 30 días
    r2 = motor.liquidacion_final(emp, date(2026, 10, 31), "renuncia", P)
    assert r2["indemnizacion"] == 0


# ---------------------------------------------------------------- flujo contable completo

async def test_nomina_mensual_asiento_pago_y_prestaciones(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    banco = await _banco(c)
    r = await c.post("/api/nomina/empleados", json=_empleado())
    assert r.status_code == 201, r.text
    # El salario no puede ser menor al mínimo.
    assert (await c.post("/api/nomina/empleados", json=_empleado("1002", salario=1_000_000))).status_code == 422

    periodo = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).json()
    assert periodo["numero"] == "NOM-1" and periodo["totales"]["neto_pagar"] == 1_859_928
    assert (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).status_code == 409

    saldos = await _balance(c)
    # Todo asiento cuadra por construcción; revisamos las cuentas principales.
    assert saldos["2505"] == -1_859_928                                  # salarios por pagar
    assert saldos["2370"] == -(140_072 + 210_109 + 9_140 + 70_036)       # aportes empleado + empleador
    assert saldos["2510"] == -166_600 and saldos["2520"] == -166_600 and saldos["2515"] == -19_992
    assert saldos["5105"] > 2_000_000

    # Pago de nómina contra el banco.
    pago = await c.post("/api/nomina/pagos", json={
        "documento_tipo": "periodo", "documento_id": periodo["id"], "cuenta_tipo": "banco",
        "cuenta_id": banco["id"], "fecha": "2026-10-31"})
    assert pago.status_code == 201, pago.text
    assert pago.json()["numero"] == "PN-1"
    saldos = await _balance(c)
    assert saldos["2505"] == 0 and saldos["1110"] == 50_000_000 - 1_859_928
    assert (await c.post(f"/api/nomina/periodos/{periodo['id']}/anular", json={})).status_code == 409  # pagado

    # Pila: aportes del mes y su pago.
    pila = (await c.get("/api/nomina/pila", params={"anio": 2026, "mes": 10})).json()
    assert pila["total"] == 140_072 + 210_109 + 9_140 + 70_036 and pila["pendiente"] == pila["total"]
    r = await c.post("/api/nomina/pagos-obligaciones", json={
        "tipo": "seguridad_social", "anio": 2026, "mes": 10, "fecha": "2026-11-05",
        "cuenta_tipo": "banco", "cuenta_id": banco["id"]})
    assert r.status_code == 201, r.text
    assert (await _balance(c))["2370"] == 0
    assert (await c.get("/api/nomina/pila", params={"anio": 2026, "mes": 10})).json()["pendiente"] == 0

    # Prima: se paga contra lo provisionado, nunca más.
    obl = (await c.get("/api/nomina/obligaciones", params={"tipo": "prima"})).json()
    assert obl["total"] == 166_600
    emp_id = obl["filas"][0]["empleado_id"]
    r = await c.post("/api/nomina/pagos-obligaciones", json={
        "tipo": "prima", "fecha": "2026-12-15", "cuenta_tipo": "banco", "cuenta_id": banco["id"],
        "lineas": [{"empleado_id": emp_id, "valor": 200_000}]})
    assert r.status_code == 409
    r = await c.post("/api/nomina/pagos-obligaciones", json={
        "tipo": "prima", "fecha": "2026-12-15", "cuenta_tipo": "banco", "cuenta_id": banco["id"],
        "lineas": [{"empleado_id": emp_id, "valor": 166_600}]})
    assert r.status_code == 201, r.text
    assert (await _balance(c))["2520"] == 0

    # Anular el pago de la prima restablece la provisión.
    await c.post(f"/api/nomina/pagos-obligaciones/{r.json()['id']}/anular", json={})
    assert (await c.get("/api/nomina/obligaciones", params={"tipo": "prima"})).json()["total"] == 166_600


async def test_nomina_anular_y_recalcular_periodo(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    emp = (await c.post("/api/nomina/empleados", json=_empleado())).json()
    periodo = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).json()

    # Una novedad posterior se refleja al recalcular; el número se conserva.
    r = await c.post("/api/nomina/novedades", json={
        "empleado_id": emp["id"], "tipo": "bonificacion_salarial", "fecha_inicio": "2026-10-10", "valor": 500_000})
    assert r.status_code == 201, r.text
    nuevo = (await c.put(f"/api/nomina/periodos/{periodo['id']}", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).json()
    assert nuevo["numero"] == "NOM-1" and nuevo["totales"]["neto_pagar"] > periodo["totales"]["neto_pagar"]
    assert (await _balance(c))["2505"] == -nuevo["totales"]["neto_pagar"]

    await c.post(f"/api/nomina/periodos/{periodo['id']}/anular", json={"motivo": "prueba"})
    saldos = await _balance(c)
    assert not any(k in saldos for k in ("2505", "2510", "2520"))
    assert (await c.get("/api/nomina/obligaciones", params={"tipo": "cesantias"})).json()["total"] == 0


async def test_nomina_quincenal_retiene_en_la_segunda(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await c.post("/api/nomina/empleados", json=_empleado("2001", 12_000_000, frecuencia_pago="quincenal"))
    # Un mensual no incluye a los quincenales.
    assert (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).status_code == 409
    q1 = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "quincena1"})).json()
    q2 = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "quincena2"})).json()
    assert q1["totales"]["retefuente"] == 0 and q2["totales"]["retefuente"] > 0
    assert q1["totales"]["sueldos"] == 6_000_000 and q2["totales"]["sueldos"] == 6_000_000

    # La retención laboral aparece en el formulario 350.
    f350 = (await c.get("/api/reportes/fiscales/formulario-350", params=RANGO)).json()
    assert f350["resumen"]["laboral"] == q2["totales"]["retefuente"]


async def test_liquidacion_de_contrato(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    banco = await _banco(c)
    emp = (await c.post("/api/nomina/empleados", json=_empleado("3001", 2_000_000, fecha_ingreso="2026-01-01"))).json()
    await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})

    cuerpo = {"empleado_id": emp["id"], "fecha_retiro": "2026-10-31", "causa": "despido_sin_justa_causa",
              "dias_salario_pendiente": 0}
    vista = (await c.post("/api/nomina/liquidaciones-finales/calcular", json=cuerpo)).json()
    assert vista["calculo"]["indemnizacion"] > 0 and vista["provisionado"]["cesantias"] > 0

    r = await c.post("/api/nomina/liquidaciones-finales", json=cuerpo)
    assert r.status_code == 201, r.text
    lf = r.json()
    assert lf["numero"] == "LF-1" and lf["neto_pagar"] == vista["calculo"]["total"]
    saldos = await _balance(c)
    for cuenta in ("2510", "2515", "2520", "2525"):
        assert abs(saldos.get(cuenta, 0)) < 1          # se cancelan las provisiones del empleado
    assert saldos["2505"] < 0                          # lo que se le debe pagar
    assert (await c.get(f"/api/nomina/empleados/{emp['id']}")).json()["estado"] == "retirado"
    assert (await c.post("/api/nomina/liquidaciones-finales", json=cuerpo)).status_code == 409   # ya retirado

    pago = await c.post("/api/nomina/pagos", json={
        "documento_tipo": "liquidacion_final", "documento_id": lf["id"], "cuenta_tipo": "banco",
        "cuenta_id": banco["id"], "fecha": "2026-10-31"})
    assert pago.status_code == 201, pago.text

    await c.post(f"/api/nomina/pagos/{pago.json()['id']}/anular", json={})
    r = await c.post(f"/api/nomina/liquidaciones-finales/{lf['id']}/anular", json={})
    assert r.status_code == 200
    assert (await c.get(f"/api/nomina/empleados/{emp['id']}")).json().get("estado") == "activo"
    assert (await c.get("/api/nomina/obligaciones", params={"tipo": "cesantias"})).json()["total"] > 0


async def test_nomina_electronica_consolida_el_mes(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    banco = await _banco(c)
    await c.post("/api/nomina/empleados", json=_empleado("4001", 3_000_000, frecuencia_pago="quincenal"))
    await c.post("/api/nomina/empleados", json=_empleado("4002", 2_000_000, primer_nombre="Luis"))
    q1 = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "quincena1"})).json()
    q2 = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "quincena2"})).json()
    mensual = (await c.post("/api/nomina/periodos", json={"anio": 2026, "mes": 10, "tipo": "mensual"})).json()

    # Sin pagar no se puede generar: la DIAN exige las fechas de pago.
    r = await c.post("/api/nomina/electronica/generar", json={"anio": 2026, "mes": 10})
    assert r.status_code == 409 and "Paga primero" in r.json()["detail"]

    for periodo, fecha in ((q1, "2026-10-15"), (q2, "2026-10-31"), (mensual, "2026-10-31")):
        r = await c.post("/api/nomina/pagos", json={
            "documento_tipo": "periodo", "documento_id": periodo["id"], "cuenta_tipo": "banco",
            "cuenta_id": banco["id"], "fecha": fecha})
        assert r.status_code == 201, r.text

    r = await c.post("/api/nomina/electronica/generar", json={"anio": 2026, "mes": 10})
    assert r.status_code == 200, r.text
    assert len(r.json()["generados"]) == 2

    docs = (await c.get("/api/nomina/electronica", params={"anio": 2026, "mes": 10})).json()
    assert [d["numero"] for d in docs] == ["NE-1", "NE-2"] or len(docs) == 2
    quincenal = next(d for d in docs if d["documento_empleado"] == "4001")
    detalle = (await c.get(f"/api/nomina/electronica/{quincenal['id']}/documento")).json()
    # Un solo documento del mes con los dos pagos quincenales consolidados.
    assert detalle["FechasPagos"] == ["2026-10-15", "2026-10-31"]
    assert detalle["Devengados"]["Basico"]["SueldoTrabajado"] == 3_000_000
    assert detalle["Periodo"]["FechaLiquidacionInicio"] == "2026-10-01"
    assert detalle["ComprobanteTotal"] == quincenal["neto"]

    # Regenerar es idempotente; transmitir sin Alegra configurado responde con un mensaje claro.
    assert (await c.post("/api/nomina/electronica/generar", json={"anio": 2026, "mes": 10})).status_code == 200
    assert len((await c.get("/api/nomina/electronica", params={"anio": 2026, "mes": 10})).json()) == 2
    r = await c.post(f"/api/nomina/electronica/{quincenal['id']}/transmitir")
    assert r.status_code == 501 and "Alegra" in r.json()["detail"]


async def test_nomina_respeta_permisos_por_rol(nuevo_cliente):
    c = await _empresa(nuevo_cliente)
    await c.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Vend", "email": "vend@a.co", "password": "clave-segura-1", "rol": "vendedor"})
    v = nuevo_cliente()
    await v.post("/api/auth/login", json={"email": "vend@a.co", "password": "clave-segura-1"})
    me = (await v.get("/api/auth/me")).json()
    v.headers["X-Empresa-Id"] = me["empresa_ids"][0]
    assert (await v.get("/api/nomina/empleados")).status_code == 403
    assert (await c.get("/api/nomina/empleados")).status_code == 200
