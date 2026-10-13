"""Valor en letras para los documentos (formato colombiano: «Son: un millón de pesos M/CTE»)."""

_UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
             "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós",
             "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos",
             "ochocientos", "novecientos"]


def _menor_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    c, resto = divmod(n, 100)
    partes = [_CENTENAS[c]] if c else []
    if resto < 30:
        if resto:
            partes.append(_UNIDADES[resto])
    else:
        d, u = divmod(resto, 10)
        partes.append(_DECENAS[d] + (f" y {_UNIDADES[u]}" if u else ""))
    return " ".join(partes)


def apocopar(texto: str) -> str:
    """«uno» -> «un» y «veintiuno» -> «veintiún» cuando van antes de un sustantivo (un peso, veintiún mil)."""
    if texto.endswith("veintiuno"):
        return texto[: -len("veintiuno")] + "veintiún"
    if texto == "uno" or texto.endswith(" uno"):
        return texto[:-3] + "un"
    return texto


def entero_a_letras(n: int) -> str:
    """Número entero no negativo en letras (hasta billones)."""
    if n == 0:
        return "cero"
    if n < 0:
        return "menos " + entero_a_letras(-n)
    partes = []
    billones, n = divmod(n, 10**12)
    if billones:
        partes.append("un billón" if billones == 1 else f"{apocopar(entero_a_letras(billones))} billones")
    millones, n = divmod(n, 10**6)
    if millones:
        partes.append("un millón" if millones == 1 else f"{apocopar(entero_a_letras(millones))} millones")
    miles, resto = divmod(n, 1000)
    if miles:
        partes.append("mil" if miles == 1 else f"{apocopar(_menor_mil(miles))} mil")
    if resto:
        partes.append(_menor_mil(resto))
    return " ".join(partes)


def valor_en_letras(valor: float, moneda: str = "pesos", sufijo: str = "M/CTE") -> str:
    """«Son: dos millones cien mil pesos con cincuenta centavos M/CTE.»"""
    centavos_total = round(abs(float(valor)) * 100)
    pesos, centavos = divmod(centavos_total, 100)
    texto = apocopar(entero_a_letras(pesos))
    if pesos and pesos % 10**6 == 0:
        texto += " de"                      # «un millón de pesos», «dos mil millones de pesos»
    salida = f"{texto} {'peso' if pesos == 1 else moneda}"
    if centavos:
        salida += f" con {apocopar(entero_a_letras(centavos))} centavo{'s' if centavos != 1 else ''}"
    return f"Son: {salida} {sufijo}"
