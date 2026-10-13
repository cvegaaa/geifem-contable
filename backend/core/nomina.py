"""Motor de cálculo de nómina colombiana (funciones puras, sin base de datos).

Todos los parámetros que cambian cada año o por norma (salario mínimo, auxilio de
transporte, UVT, divisor de horas, recargos, porcentajes de aportes) viven en una
tabla por año que la empresa puede ajustar. Los valores por defecto son un punto
de partida y **deben verificarse** con la norma vigente y con el contador.

Convenciones:
- Mes comercial de 30 días; quincena de 15.
- Los valores se redondean al peso.
- Procedimiento 1 de retención en la fuente laboral (art. 383 ET), calculado sobre el
  acumulado del mes (en nómina quincenal se practica en la segunda quincena).
"""
from calendar import monthrange
from datetime import date
from core.dinero import redondear

# Valores por defecto de 2026 (verificar: decretos de salario mínimo y auxilio, UVT, Ley 2101 y Ley 2466).
PARAMETROS_2026: dict = {
    "anio": 2026,
    "smmlv": 1_750_905,
    "aux_transporte": 249_095,
    "uvt": 52_374,
    "horas_mes": 210,  # jornada de 42 horas semanales desde el 15 de julio de 2026
    "tope_aux_smmlv": 2,
    "ibc_max_smmlv": 25,
    "salud_empleado": 4.0,
    "pension_empleado": 4.0,
    "salud_empleador": 8.5,
    "pension_empleador": 12.0,
    "caja": 4.0,
    "sena": 2.0,
    "icbf": 3.0,
    "arl": {"I": 0.522, "II": 1.044, "III": 2.436, "IV": 4.350, "V": 6.960},
    "exonerado_114_1": True,
    "tope_exoneracion_smmlv": 10,
    "cesantias": 8.33,
    "intereses_cesantias": 12.0,
    "prima": 8.33,
    "vacaciones": 4.17,
    "incapacidad_porcentaje": 66.67,
    # Factor de pago sobre el valor de la hora ordinaria. Los recargos solos (nocturno, dominical)
    # se suman al salario mensual; las horas extra se pagan completas.
    "recargos": {
        "hora_extra_diurna": 1.25,
        "hora_extra_nocturna": 1.75,
        "recargo_nocturno": 0.35,
        "recargo_dominical_festivo": 0.90,  # 90% desde el 1 de julio de 2026 (Ley 2466 de 2025)
        "hora_extra_diurna_dominical": 2.15,
        "hora_extra_nocturna_dominical": 2.65,
        "recargo_nocturno_dominical": 1.25,
    },
    # Fondo de solidaridad pensional: [desde SMMLV, hasta SMMLV, %]
    "fsp": [[4, 16, 1.0], [16, 17, 1.2], [17, 18, 1.4], [18, 19, 1.6], [19, 20, 1.8], [20, None, 2.0]],
    # Art. 383 ET: [desde UVT, hasta UVT, tarifa marginal %, UVT adicionales]
    "tabla_retefuente": [
        [0, 95, 0, 0], [95, 150, 19, 0], [150, 360, 28, 10], [360, 640, 33, 69],
        [640, 945, 35, 162], [945, 2300, 37, 268], [2300, None, 39, 770],
    ],
    "renta_exenta_25_tope_uvt_anual": 790,
    "tope_deducciones_uvt_anual": 1340,
    "dependientes_tope_uvt_mensual": 32,
    "vivienda_tope_uvt_mensual": 100,
    "salud_prepagada_tope_uvt_mensual": 16,
    "verificado": False,
}

TIPOS_HORAS = list(PARAMETROS_2026["recargos"])
TIPOS_DEVENGO_VALOR = ["comision", "bonificacion_salarial", "bonificacion_no_salarial", "otro_devengo_no_salarial"]
TIPOS_DEDUCCION = ["prestamo", "embargo", "libranza", "otra_deduccion"]
TIPOS_DIAS = [
    "incapacidad_general", "incapacidad_laboral", "licencia_maternidad_paternidad",
    "licencia_remunerada", "vacaciones", "licencia_no_remunerada", "suspension",
]
TIPOS_NOVEDAD = TIPOS_HORAS + TIPOS_DEVENGO_VALOR + TIPOS_DEDUCCION + TIPOS_DIAS


def r(v: float) -> float:
    return redondear(v, 0)


def parametros_anio(anio: int, guardado: dict | None = None) -> dict:
    base = {**PARAMETROS_2026, "anio": anio}
    if anio != 2026:
        base["verificado"] = False
    if guardado:
        base.update({k: v for k, v in guardado.items() if k in PARAMETROS_2026 and v is not None})
    return base


# ---------------------------------------------------------------------------
# Fechas (base 360)
# ---------------------------------------------------------------------------

def _dia30(d: date) -> int:
    if d.month == 2 and d.day == monthrange(d.year, 2)[1]:
        return 30
    return min(d.day, 30)


def dias360(a: date, b: date) -> int:
    """Días entre dos fechas con el mes comercial de 30 días (sin contar el primer día)."""
    return (b.year - a.year) * 360 + (b.month - a.month) * 30 + (_dia30(b) - _dia30(a))


def dias_comerciales(inicio: date, fin: date) -> int:
    """Días inclusivos entre dos fechas con mes de 30 días."""
    if fin < inicio:
        return 0
    return dias360(inicio, fin) + 1


def rango_periodo(anio: int, mes: int, tipo: str) -> tuple[date, date, int]:
    ultimo = monthrange(anio, mes)[1]
    if tipo == "quincena1":
        return date(anio, mes, 1), date(anio, mes, 15), 15
    if tipo == "quincena2":
        return date(anio, mes, 16), date(anio, mes, ultimo), 15
    return date(anio, mes, 1), date(anio, mes, ultimo), 30


# ---------------------------------------------------------------------------
# Retención en la fuente laboral (procedimiento 1)
# ---------------------------------------------------------------------------

def retefuente_laboral(ingresos: float, aportes_obligatorios: float, emp: dict, p: dict) -> float:
    """Retención mensual por rentas de trabajo. `ingresos`: total laboral gravable del mes."""
    uvt = p["uvt"]
    subtotal = max(0.0, ingresos - aportes_obligatorios)
    if subtotal <= 0:
        return 0.0
    deducciones = 0.0
    if emp.get("dependientes"):
        deducciones += min(ingresos * 0.10, p["dependientes_tope_uvt_mensual"] * uvt)
    deducciones += min(float(emp.get("deduccion_vivienda") or 0), p["vivienda_tope_uvt_mensual"] * uvt)
    deducciones += min(float(emp.get("medicina_prepagada") or 0), p["salud_prepagada_tope_uvt_mensual"] * uvt)
    exenta = min((subtotal - deducciones) * 0.25, p["renta_exenta_25_tope_uvt_anual"] / 12 * uvt)
    exenta = max(0.0, exenta)
    tope = min(subtotal * 0.40, p["tope_deducciones_uvt_anual"] / 12 * uvt)
    base = subtotal - min(deducciones + exenta, tope)
    base_uvt = base / uvt
    impuesto_uvt = 0.0
    for desde, hasta, tarifa, adicional in p["tabla_retefuente"]:
        if base_uvt > desde and (hasta is None or base_uvt <= hasta):
            impuesto_uvt = (base_uvt - desde) * tarifa / 100 + adicional
            break
    return float(redondear(impuesto_uvt * uvt, -3))  # se aproxima al múltiplo de mil


def porcentaje_fsp(ibc_mensual: float, p: dict) -> float:
    ratio = ibc_mensual / p["smmlv"]
    for desde, hasta, pct in p["fsp"]:
        if ratio >= desde and (hasta is None or ratio < hasta):
            return pct
    return 0.0


# ---------------------------------------------------------------------------
# Liquidación de un empleado en un periodo
# ---------------------------------------------------------------------------

def _suma(novs: list[dict], tipo: str, campo: str) -> float:
    return sum(float(n.get(campo) or 0) for n in novs if n["tipo"] == tipo)


def liquidar_empleado(
    emp: dict, novedades: list[dict], inicio: date, fin: date, dias_periodo: int, p: dict,
    previo_mes: dict | None = None, es_ultimo_periodo_mes: bool = True,
) -> dict:
    """Liquida a un empleado en el periodo [inicio, fin].

    `previo_mes`: liquidación de la primera quincena del mismo mes (para la retención acumulada).
    """
    smmlv = p["smmlv"]
    salario = float(emp["salario_basico"])
    integral = bool(emp.get("salario_integral"))
    sal_dia = salario / 30
    valor_hora = salario / p["horas_mes"]

    # Días activos dentro del periodo (ingreso y retiro parciales).
    ingreso = date.fromisoformat(emp["fecha_ingreso"]) if emp.get("fecha_ingreso") else inicio
    retiro = date.fromisoformat(emp["fecha_retiro"]) if emp.get("fecha_retiro") else None
    a, b = max(inicio, ingreso), min(fin, retiro) if retiro else fin
    dias_activos = min(dias_periodo, dias_comerciales(a, b))

    d = {t: _suma(novedades, t, "cantidad") for t in TIPOS_DIAS}
    dias_pagados_aparte = sum(d[t] for t in (
        "incapacidad_general", "incapacidad_laboral", "licencia_maternidad_paternidad", "licencia_remunerada", "vacaciones"))
    dias_sin_pago = d["licencia_no_remunerada"] + d["suspension"]
    dias_trabajados = max(0.0, dias_activos - dias_pagados_aparte - dias_sin_pago)

    sueldo = r(sal_dia * dias_trabajados)
    vacaciones = r(sal_dia * d["vacaciones"])
    licencia_rem = r(sal_dia * d["licencia_remunerada"])

    # Incapacidades y licencias a cargo de EPS/ARL (el empleador las adelanta y recobra).
    piso_dia = smmlv / 30
    valor_dia_inc = max(sal_dia * p["incapacidad_porcentaje"] / 100, piso_dia)
    incap_empleador = incap_eps = 0.0
    for n in novedades:
        if n["tipo"] != "incapacidad_general":
            continue
        dias = float(n.get("cantidad") or 0)
        previos = float(n.get("dias_previos") or 0)
        dias_emp = max(0.0, min(dias, 2 - previos))
        incap_empleador += dias_emp * valor_dia_inc
        incap_eps += (dias - dias_emp) * valor_dia_inc
    incap_laboral = d["incapacidad_laboral"] * sal_dia
    licencia_mat = d["licencia_maternidad_paternidad"] * sal_dia
    incap_empleador, incap_eps = r(incap_empleador), r(incap_eps + incap_laboral + licencia_mat)

    # Horas extra y recargos.
    horas: dict[str, float] = {}
    for t in TIPOS_HORAS:
        cant = _suma(novedades, t, "cantidad")
        if cant:
            horas[t] = r(cant * valor_hora * p["recargos"][t])
    total_horas = sum(horas.values())

    comisiones = r(_suma(novedades, "comision", "valor"))
    bonif_sal = r(_suma(novedades, "bonificacion_salarial", "valor"))
    no_salariales = r(_suma(novedades, "bonificacion_no_salarial", "valor") + _suma(novedades, "otro_devengo_no_salarial", "valor"))

    variables = total_horas + comisiones + bonif_sal
    devengado_salarial = sueldo + vacaciones + licencia_rem + incap_empleador + incap_eps + variables

    aux = 0.0
    if not integral and salario <= p["tope_aux_smmlv"] * smmlv:
        aux = r(p["aux_transporte"] / 30 * dias_trabajados)

    # Ingreso base de cotización
    if integral:
        ibc = r(0.7 * sal_dia * dias_activos)
    else:
        total_rem = devengado_salarial + no_salariales
        exceso_no_salarial = max(0.0, no_salariales - 0.40 * total_rem)
        ibc = devengado_salarial + exceso_no_salarial
    ibc_min = smmlv * dias_activos / 30
    ibc_max = p["ibc_max_smmlv"] * smmlv * dias_activos / 30
    ibc = r(min(max(ibc, ibc_min), ibc_max)) if dias_activos > 0 else 0.0

    salud = r(ibc * p["salud_empleado"] / 100)
    pension = r(ibc * p["pension_empleado"] / 100)
    ibc_mensual = ibc * 30 / dias_activos if dias_activos else 0
    fsp = r(ibc * porcentaje_fsp(ibc_mensual, p) / 100)

    otras: list[dict] = []
    for t in TIPOS_DEDUCCION:
        v = r(_suma(novedades, t, "valor"))
        if v:
            otras.append({"tipo": t, "valor": v})
    total_otras = sum(o["valor"] for o in otras)

    total_devengado = devengado_salarial + aux + no_salariales
    aportes_oblig = salud + pension + fsp

    # Retención en la fuente: sobre el acumulado del mes, en el último periodo del mes.
    retefuente = 0.0
    if es_ultimo_periodo_mes:
        ingresos_mes = total_devengado + (previo_mes["total_devengado"] if previo_mes else 0)
        aportes_mes = aportes_oblig + (previo_mes["aportes_obligatorios"] if previo_mes else 0)
        ya_retenido = previo_mes["deducciones"]["retefuente"] if previo_mes else 0
        retefuente = max(0.0, retefuente_laboral(ingresos_mes, aportes_mes, emp, p) - ya_retenido)

    total_deducciones = aportes_oblig + retefuente + total_otras
    neto = total_devengado - total_deducciones

    # Aportes del empleador
    base_mes_eq = devengado_salarial * 30 / dias_activos if dias_activos else 0
    exonerado = p["exonerado_114_1"] and base_mes_eq < p["tope_exoneracion_smmlv"] * smmlv
    aportes_empleador = {
        "salud": 0.0 if exonerado else r(ibc * p["salud_empleador"] / 100),
        "pension": r(ibc * p["pension_empleador"] / 100),
        "arl": r(ibc * p["arl"].get(emp.get("riesgo_arl", "I"), p["arl"]["I"]) / 100),
        "caja": r(devengado_salarial * p["caja"] / 100),
        "sena": 0.0 if exonerado else r(devengado_salarial * p["sena"] / 100),
        "icbf": 0.0 if exonerado else r(devengado_salarial * p["icbf"] / 100),
    }

    # Provisiones de prestaciones sociales
    base_prest = devengado_salarial - incap_eps + aux
    provisiones = {"cesantias": 0.0, "intereses": 0.0, "prima": 0.0}
    if not integral:
        provisiones["cesantias"] = r(base_prest * p["cesantias"] / 100)
        provisiones["intereses"] = r(provisiones["cesantias"] * p["intereses_cesantias"] / 100)
        provisiones["prima"] = r(base_prest * p["prima"] / 100)
    provisiones["vacaciones"] = r(sueldo * p["vacaciones"] / 100)

    return {
        "empleado_id": emp["id"],
        "nombre": nombre_empleado(emp),
        "documento": emp.get("numero_documento", ""),
        "dias_periodo": dias_periodo,
        "dias_activos": dias_activos,
        "dias_trabajados": dias_trabajados,
        "dias_novedades": {t: v for t, v in d.items() if v},
        "salario_basico": salario,
        "devengos": {
            "sueldo": sueldo, "aux_transporte": aux, "vacaciones": vacaciones, "licencia_remunerada": licencia_rem,
            "incapacidad_empleador": incap_empleador, "incapacidad_a_cargo_eps_arl": incap_eps,
            "horas": horas, "comisiones": comisiones, "bonificacion_salarial": bonif_sal,
            "no_salariales": no_salariales,
        },
        "devengado_salarial": devengado_salarial,
        "total_devengado": total_devengado,
        "ibc": ibc,
        "aportes_obligatorios": aportes_oblig,
        "deducciones": {"salud": salud, "pension": pension, "fsp": fsp, "retefuente": retefuente, "otras": otras},
        "total_deducciones": total_deducciones,
        "neto_pagar": neto,
        "aportes_empleador": aportes_empleador,
        "exonerado_114_1": bool(exonerado),
        "provisiones": provisiones,
    }


def nombre_empleado(emp: dict) -> str:
    partes = [emp.get("primer_nombre"), emp.get("otros_nombres"), emp.get("primer_apellido"), emp.get("segundo_apellido")]
    return " ".join(x for x in partes if x)


def totales_periodo(lineas: list[dict]) -> dict:
    """Totales del periodo: lo que alimenta el asiento, el pago y los reportes."""
    def s(f):
        return r(sum(f(l) for l in lineas))

    horas = s(lambda l: sum(l["devengos"]["horas"].values()))
    return {
        "empleados": len(lineas),
        "sueldos": s(lambda l: l["devengos"]["sueldo"] + l["devengos"]["vacaciones"] + l["devengos"]["licencia_remunerada"]
                     + l["devengos"]["incapacidad_empleador"] + l["devengos"]["comisiones"]
                     + l["devengos"]["bonificacion_salarial"] + l["devengos"]["no_salariales"]),
        "horas_extra": horas,
        "aux_transporte": s(lambda l: l["devengos"]["aux_transporte"]),
        "a_cargo_eps_arl": s(lambda l: l["devengos"]["incapacidad_a_cargo_eps_arl"]),
        "total_devengado": s(lambda l: l["total_devengado"]),
        "salud_empleado": s(lambda l: l["deducciones"]["salud"]),
        "pension_empleado": s(lambda l: l["deducciones"]["pension"]),
        "fsp": s(lambda l: l["deducciones"]["fsp"]),
        "retefuente": s(lambda l: l["deducciones"]["retefuente"]),
        "prestamos": s(lambda l: sum(o["valor"] for o in l["deducciones"]["otras"] if o["tipo"] == "prestamo")),
        "otras_deducciones": s(lambda l: sum(o["valor"] for o in l["deducciones"]["otras"] if o["tipo"] != "prestamo")),
        "total_deducciones": s(lambda l: l["total_deducciones"]),
        "neto_pagar": s(lambda l: l["neto_pagar"]),
        "seguridad_social_empleador": s(lambda l: l["aportes_empleador"]["salud"] + l["aportes_empleador"]["pension"]
                                        + l["aportes_empleador"]["arl"]),
        "parafiscales": s(lambda l: l["aportes_empleador"]["caja"] + l["aportes_empleador"]["sena"] + l["aportes_empleador"]["icbf"]),
        "cesantias": s(lambda l: l["provisiones"]["cesantias"]),
        "intereses": s(lambda l: l["provisiones"]["intereses"]),
        "prima": s(lambda l: l["provisiones"]["prima"]),
        "vacaciones": s(lambda l: l["provisiones"]["vacaciones"]),
    }


# ---------------------------------------------------------------------------
# Liquidación final de contrato
# ---------------------------------------------------------------------------

def liquidacion_final(
    emp: dict, fecha_retiro: date, causa: str, p: dict, dias_salario_pendiente: float = 0,
    dias_vacaciones_disfrutados: float = 0, promedio_variable: float = 0, indemnizacion: float | None = None,
    fecha_fin_contrato: date | None = None,
) -> dict:
    """Prestaciones y demás valores a pagar al terminar el contrato (base 360 días)."""
    salario = float(emp["salario_basico"])
    integral = bool(emp.get("salario_integral"))
    ingreso = date.fromisoformat(emp["fecha_ingreso"])
    aux = p["aux_transporte"] if (not integral and salario <= p["tope_aux_smmlv"] * p["smmlv"]) else 0
    base_prest = salario + aux + promedio_variable

    inicio_ces = max(ingreso, date(fecha_retiro.year, 1, 1))
    dias_ces = dias_comerciales(inicio_ces, fecha_retiro)
    inicio_prima = max(ingreso, date(fecha_retiro.year, 1 if fecha_retiro.month <= 6 else 7, 1))
    dias_prima = dias_comerciales(inicio_prima, fecha_retiro)
    dias_laborados = dias_comerciales(ingreso, fecha_retiro)

    cesantias = r(base_prest * dias_ces / 360) if not integral else 0.0
    intereses = r(cesantias * dias_ces * p["intereses_cesantias"] / 100 / 360)
    prima = r(base_prest * dias_prima / 360) if not integral else 0.0
    dias_vac_causados = dias_laborados * 15 / 360
    dias_vac_pend = max(0.0, dias_vac_causados - dias_vacaciones_disfrutados)
    vacaciones = r(salario / 30 * dias_vac_pend)
    salario_pendiente = r(salario / 30 * dias_salario_pendiente)

    if indemnizacion is None:
        indemnizacion = r(_indemnizacion(emp, causa, fecha_retiro, fecha_fin_contrato, p))

    return {
        "base_prestaciones": r(base_prest),
        "dias": {"cesantias": dias_ces, "prima": dias_prima, "laborados": dias_laborados,
                 "vacaciones_causados": redondear(dias_vac_causados, 2), "vacaciones_pendientes": redondear(dias_vac_pend, 2)},
        "salario_pendiente": salario_pendiente,
        "cesantias": cesantias, "intereses": intereses, "prima": prima, "vacaciones": vacaciones,
        "indemnizacion": indemnizacion,
        "total": r(salario_pendiente + cesantias + intereses + prima + vacaciones + indemnizacion),
    }


def _indemnizacion(emp: dict, causa: str, retiro: date, fin_contrato: date | None, p: dict) -> float:
    """Art. 64 CST (sin justa causa). Indefinido: 30 días el primer año y 20 por cada año adicional
    (salarios menores a 10 SMMLV). Fijo: lo que falta del plazo, mínimo 15 días."""
    if causa != "despido_sin_justa_causa":
        return 0.0
    sal_dia = float(emp["salario_basico"]) / 30
    if emp.get("tipo_contrato") == "fijo" and fin_contrato:
        faltantes = max(15, dias_comerciales(retiro, fin_contrato) - 1)
        return sal_dia * faltantes
    dias_lab = dias_comerciales(date.fromisoformat(emp["fecha_ingreso"]), retiro)
    anios = dias_lab / 360
    dias = 30 if anios <= 1 else 30 + (anios - 1) * 20
    if float(emp["salario_basico"]) >= 10 * p["smmlv"]:
        dias = 20 if anios <= 1 else 20 + (anios - 1) * 15
    return sal_dia * dias
