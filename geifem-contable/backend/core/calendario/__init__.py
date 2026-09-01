"""Calendario tributario — Fase 3.

Genera las fechas límite de las obligaciones fiscales de una empresa a
partir de su NIT (último / últimos dos dígitos) y su régimen tributario.

IMPORTANTE: las fechas se calculan con los patrones históricos de la DIAN
(día base por dígito + ajuste al siguiente día hábil). Cada año la DIAN
expide un decreto con el calendario oficial; los valores aquí son
referenciales y deben verificarse contra ese decreto. La tabla
`TABLAS_DIA` permite ajustar los días base sin tocar la lógica.
"""
from datetime import date, timedelta

# Día base de vencimiento según último dígito del NIT (patrón histórico
# de retención / IVA; verificar decreto anual de la DIAN).
DIA_ULTIMO_DIGITO = {1: 9, 2: 10, 3: 11, 4: 12, 5: 13, 6: 14, 7: 15, 8: 16, 9: 17, 0: 18}

MESES_BIMESTRALES = [
    ("Enero - Febrero", 3),
    ("Marzo - Abril", 5),
    ("Mayo - Junio", 7),
    ("Julio - Agosto", 9),
    ("Septiembre - Octubre", 11),
    ("Noviembre - Diciembre", 13),  # vence en enero del año siguiente
]

MESES_CUATRIMESTRALES = [
    ("Enero - Abril", 5),
    ("Mayo - Agosto", 9),
    ("Septiembre - Diciembre", 13),  # vence en enero del año siguiente
]

FESTIVOS_CO = set()  # placeholder: cargar festivos oficiales por año si se requiere


def _dia_habil(fecha: date) -> date:
    """Desplaza al siguiente día hábil (lunes-viernes). Festivos: placeholder."""
    while fecha.weekday() >= 5 or fecha.isoformat() in FESTIVOS_CO:
        fecha += timedelta(days=1)
    return fecha


def _fecha_mes(anio: int, mes: int, dia: int) -> date:
    """Fecha ajustada a día hábil; mes 13 = enero del año siguiente."""
    if mes > 12:
        anio, mes = anio + 1, mes - 12
    return _dia_habil(date(anio, mes, dia))


def _estado(fecha: date, hoy: date) -> tuple[str, int]:
    dias = (fecha - hoy).days
    if dias < 0:
        return "vencida", dias
    if dias <= 15:
        return "proxima", dias
    return "futura", dias


def _por_ultimo_digito(nit: str, anio: int, mes: int, hoy: date) -> dict:
    digito = int(nit[-1]) if nit and nit[-1].isdigit() else 0
    fecha = _fecha_mes(anio, mes, DIA_ULTIMO_DIGITO[digito])
    estado, dias = _estado(fecha, hoy)
    return {"fecha_limite": fecha.isoformat(), "estado": estado, "dias": dias}


def _por_dos_digitos(nit: str, anio: int, mes: int, dia_base: int, hoy: date) -> dict:
    """Obligaciones anuales escalonadas por últimos dos dígitos (01-20 -> día base..base+19)."""
    dos = int(nit[-2:]) if len(nit) >= 2 and nit[-2:].isdigit() else 1
    if dos == 0:
        dos = 20
    dia = dia_base + min(dos, 20) - 1
    fecha = _dia_habil(date(anio, mes, dia))
    estado, dias = _estado(fecha, hoy)
    return {"fecha_limite": fecha.isoformat(), "estado": estado, "dias": dias}


def calendario_empresa(nit: str, regimen: str, anio: int, hoy: date | None = None) -> list[dict]:
    """Devuelve las obligaciones del año con sus fechas límite y estado.

    regimen: "SIMPLE" | "COMUN" (cualquier otro valor se trata como COMUN).
    """
    hoy = hoy or date.today()
    regimen = (regimen or "COMUN").upper()
    obligaciones: list[dict] = []

    # Renovación del registro mercantil (comerciantes) — 31 de marzo.
    f = _dia_habil(date(anio, 3, 31))
    estado, dias = _estado(f, hoy)
    obligaciones.append({
        "codigo": "RM",
        "obligacion": "Renovación registro mercantil",
        "periodicidad": "Anual",
        "fechas": [{"periodo": f"Año {anio}", "fecha_limite": f.isoformat(), "estado": estado, "dias": dias}],
    })

    if regimen == "SIMPLE":
        # SIMPLE: anticipo bimestral (form 260) + declaración anual (junio).
        fechas = [
            {"periodo": p, **_por_ultimo_digito(nit, anio, m, hoy)}
            for p, m in MESES_BIMESTRALES
        ]
        obligaciones.append({
            "codigo": "260",
            "obligacion": "Anticipo SIMPLE (Formulario 260)",
            "periodicidad": "Bimestral",
            "fechas": fechas,
        })
        f = _por_dos_digitos(nit, anio, 6, 9, hoy)
        obligaciones.append({
            "codigo": "260A",
            "obligacion": "Declaración anual SIMPLE",
            "periodicidad": "Anual",
            "fechas": [{"periodo": f"Año {anio}", **f}],
        })
    else:
        # Régimen común: renta PJ (abril) con anticipo.
        f = _por_dos_digitos(nit, anio, 4, 10, hoy)
        obligaciones.append({
            "codigo": "110",
            "obligacion": "Declaración de renta y anticipo (personas jurídicas)",
            "periodicidad": "Anual",
            "fechas": [{"periodo": f"Año {anio}", **f}],
        })

    # Retención en la fuente mensual (Formulario 350).
    fechas = [
        {"periodo": date(anio, m, 1).strftime("%B %Y").capitalize(), **_por_ultimo_digito(nit, anio, m + 1, hoy)}
        for m in range(1, 12)  # el periodo de diciembre vence en enero del año siguiente
    ]
    fechas.append({
        "periodo": f"Diciembre {anio}",
        **_por_ultimo_digito(nit, anio, 13, hoy),
    })
    obligaciones.append({
        "codigo": "350",
        "obligacion": "Retención en la fuente (Formulario 350)",
        "periodicidad": "Mensual",
        "fechas": fechas,
    })

    # IVA bimestral (Formulario 300).
    fechas = [{"periodo": p, **_por_ultimo_digito(nit, anio, m, hoy)} for p, m in MESES_BIMESTRALES]
    obligaciones.append({
        "codigo": "300",
        "obligacion": "IVA bimestral (Formulario 300)",
        "periodicidad": "Bimestral",
        "fechas": fechas,
    })

    # IVA cuatrimestral (declarantes de menores ingresos).
    fechas = [{"periodo": p, **_por_ultimo_digito(nit, anio, m, hoy)} for p, m in MESES_CUATRIMESTRALES]
    obligaciones.append({
        "codigo": "300C",
        "obligacion": "IVA cuatrimestral (Formulario 300)",
        "periodicidad": "Cuatrimestral",
        "fechas": fechas,
    })

    # Información exógena (medios magnéticos) — mayo/junio, últimos dos dígitos.
    f = _por_dos_digitos(nit, anio, 5, 12, hoy)
    obligaciones.append({
        "codigo": "EXO",
        "obligacion": "Información exógena (formatos 1001-2276)",
        "periodicidad": "Anual",
        "fechas": [{"periodo": f"Reporte año gravable {anio - 1}", **f}],
    })

    # ICA bimestral — fecha referencial; cada municipio expide su calendario.
    fechas = [
        {"periodo": p, "fecha_limite": _fecha_mes(anio, m, 15).isoformat(),
         "estado": "verificar", "dias": None}
        for p, m in MESES_BIMESTRALES
    ]
    obligaciones.append({
        "codigo": "ICA",
        "obligacion": "Industria y comercio (ICA) — según municipio",
        "periodicidad": "Bimestral",
        "fechas": fechas,
    })

    return obligaciones


def resumen_calendario(obligaciones: list[dict]) -> dict:
    planas = [
        {**f, "obligacion": o["obligacion"], "codigo": o["codigo"]}
        for o in obligaciones for f in o["fechas"]
    ]
    planas.sort(key=lambda x: x["fecha_limite"])
    return {
        "total": len(planas),
        "vencidas": sum(1 for f in planas if f["estado"] == "vencida"),
        "proximas_30_dias": sum(
            1 for f in planas
            if f["estado"] in ("proxima",) or (f["estado"] == "futura" and f.get("dias") is not None and f["dias"] <= 30)
        ),
        "proxima_fecha": next((f for f in planas if f["estado"] in ("proxima", "futura")), None),
        "planas": planas,
    }
