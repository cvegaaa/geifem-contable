"""Plan Único de Cuentas (Decreto 2650/93) — semilla para empresas comerciales.

Incluye clases, grupos y las cuentas (4 dígitos) de uso habitual en un
comercio, entre ellas todas las que el sistema usa en sus asientos
automáticos (1105, 1110, 1305, 1435, 2205, 2365, 2367, 2368, 2408, 4135,
6135, 6205). Es la misma para régimen ordinario y SIMPLE: la
responsabilidad de IVA se configura aparte en la empresa. Cada empresa
puede ampliarla desde `configuracion/plan-cuentas`.
"""

D, C = "debito", "credito"

# (codigo, nombre, naturaleza)
_CUENTAS: list[tuple[str, str, str]] = [
    ("1", "ACTIVO", D),
    ("11", "DISPONIBLE", D),
    ("1105", "Caja", D),
    ("1110", "Bancos", D),
    ("1120", "Cuentas de ahorro", D),
    ("13", "DEUDORES", D),
    ("1305", "Clientes", D),
    ("1330", "Anticipos y avances", D),
    ("1355", "Anticipo de impuestos y contribuciones o saldos a favor", D),
    ("1365", "Cuentas por cobrar a trabajadores", D),
    ("1380", "Deudores varios", D),
    ("1399", "Provisiones (deudores)", C),
    ("14", "INVENTARIOS", D),
    ("1435", "Mercancías no fabricadas por la empresa", D),
    ("15", "PROPIEDADES, PLANTA Y EQUIPO", D),
    ("1516", "Construcciones y edificaciones", D),
    ("1524", "Equipo de oficina", D),
    ("1528", "Equipo de computación y comunicación", D),
    ("1540", "Flota y equipo de transporte", D),
    ("1592", "Depreciación acumulada", C),
    ("17", "DIFERIDOS", D),
    ("1705", "Gastos pagados por anticipado", D),
    ("2", "PASIVO", C),
    ("21", "OBLIGACIONES FINANCIERAS", C),
    ("2105", "Bancos nacionales", C),
    ("22", "PROVEEDORES", C),
    ("2205", "Proveedores nacionales", C),
    ("23", "CUENTAS POR PAGAR", C),
    ("2335", "Costos y gastos por pagar", C),
    ("2365", "Retención en la fuente", C),
    ("2367", "Impuesto a las ventas retenido", C),
    ("2368", "Impuesto de industria y comercio retenido", C),
    ("2370", "Retenciones y aportes de nómina", C),
    ("2380", "Acreedores varios", C),
    ("24", "IMPUESTOS, GRAVÁMENES Y TASAS", C),
    ("2404", "De renta y complementarios", C),
    ("2408", "Impuesto sobre las ventas por pagar", C),
    ("2412", "De industria y comercio", C),
    ("2495", "Impuesto nacional al consumo y otros", C),
    ("25", "OBLIGACIONES LABORALES", C),
    ("2505", "Salarios por pagar", C),
    ("2510", "Cesantías consolidadas", C),
    ("2515", "Intereses sobre cesantías", C),
    ("2520", "Prima de servicios", C),
    ("2525", "Vacaciones consolidadas", C),
    ("28", "OTROS PASIVOS", C),
    ("2805", "Anticipos y avances recibidos", C),
    ("3", "PATRIMONIO", C),
    ("31", "CAPITAL SOCIAL", C),
    ("3105", "Capital suscrito y pagado", C),
    ("3115", "Aportes sociales", C),
    ("33", "RESERVAS", C),
    ("3305", "Reservas obligatorias", C),
    ("36", "RESULTADOS DEL EJERCICIO", C),
    ("3605", "Utilidad del ejercicio", C),
    ("3610", "Pérdida del ejercicio", D),
    ("37", "RESULTADOS DE EJERCICIOS ANTERIORES", C),
    ("3705", "Utilidades acumuladas", C),
    ("3710", "Pérdidas acumuladas", D),
    ("4", "INGRESOS", C),
    ("41", "OPERACIONALES", C),
    ("4135", "Comercio al por mayor y al por menor", C),
    ("4175", "Devoluciones en ventas (DB)", D),
    ("42", "NO OPERACIONALES", C),
    ("4210", "Financieros", C),
    ("4250", "Recuperaciones", C),
    ("4295", "Diversos", C),
    ("5", "GASTOS", D),
    ("51", "OPERACIONALES DE ADMINISTRACIÓN", D),
    ("5105", "Gastos de personal", D),
    ("5110", "Honorarios", D),
    ("5115", "Impuestos", D),
    ("5120", "Arrendamientos", D),
    ("5135", "Servicios", D),
    ("5140", "Gastos legales", D),
    ("5145", "Mantenimiento y reparaciones", D),
    ("5160", "Depreciaciones", D),
    ("5195", "Diversos", D),
    ("52", "OPERACIONALES DE VENTAS", D),
    ("5205", "Gastos de personal", D),
    ("5235", "Servicios", D),
    ("5295", "Diversos", D),
    ("53", "NO OPERACIONALES", D),
    ("5305", "Financieros", D),
    ("5315", "Gastos extraordinarios", D),
    ("54", "IMPUESTO DE RENTA Y COMPLEMENTARIOS", D),
    ("5405", "Impuesto de renta y complementarios", D),
    ("6", "COSTOS DE VENTAS", D),
    ("61", "COSTO DE VENTAS Y DE PRESTACIÓN DE SERVICIOS", D),
    ("6135", "Comercio al por mayor y al por menor", D),
    ("62", "COMPRAS", D),
    ("6205", "De mercancías", D),
]

# Subcuentas auxiliares (6 dígitos) de uso habitual: (codigo, nombre). Heredan la naturaleza de su cuenta.
_AUXILIARES: list[tuple[str, str]] = [
    ("110505", "Caja general"), ("110510", "Cajas menores"), ("110515", "Moneda extranjera"),
    ("111005", "Moneda nacional"), ("111010", "Moneda extranjera"),
    ("112005", "Cuentas de ahorro nacionales"),
    ("130505", "Clientes nacionales"), ("130510", "Clientes del exterior"),
    ("143505", "Mercancías para la venta"),
    ("220505", "Proveedores nacionales"), ("220510", "Proveedores del exterior"),
    ("236505", "Salarios y pagos laborales"), ("236510", "Dividendos y participaciones"),
    ("236515", "Honorarios"), ("236520", "Comisiones"), ("236525", "Servicios"),
    ("236530", "Arrendamientos"), ("236540", "Compras"), ("236570", "Otras retenciones y patrimonio"),
    ("240805", "IVA generado"), ("240810", "IVA descontable"),
    ("280505", "Anticipos de clientes"),
    ("310505", "Capital autorizado"),
    ("413505", "Venta de mercancías"), ("413510", "Venta de servicios"),
    ("613505", "Costo de mercancías vendidas"),
    ("620505", "Compras de mercancías"),
    ("510506", "Sueldos"), ("510527", "Auxilio de transporte"), ("510530", "Cesantías"), ("510533", "Intereses sobre cesantías"),
    ("510536", "Prima de servicios"), ("510539", "Vacaciones"), ("510568", "Aportes a ARL"), ("510569", "Aportes a EPS"),
    ("510570", "Aportes a fondos de pensiones"), ("510572", "Aportes a cajas de compensación"),
    ("510575", "Aportes al ICBF"), ("510578", "SENA"),
]

_NIVEL_POR_LONGITUD = {1: 1, 2: 2, 4: 3, 6: 4}


def _padre(codigo: str) -> str | None:
    if len(codigo) == 1:
        return None
    return codigo[:1] if len(codigo) == 2 else codigo[: len(codigo) - 2]


def _auxiliares_completos() -> list[tuple[str, str, str]]:
    """Auxiliares de 6 dígitos: los definidos a mano y uno «general» (xxxx05) para cada cuenta de 4 dígitos que no tenga."""
    naturaleza = {c: n for c, _, n in _CUENTAS}
    nombre = {c: nm for c, nm, _ in _CUENTAS}
    existentes = {c for c, _ in _AUXILIARES}
    salida = [(c, nm, naturaleza.get(c[:4], D)) for c, nm in _AUXILIARES if c[:4] in naturaleza]
    con_aux = {c[:4] for c in existentes}
    for codigo in sorted(c for c in naturaleza if len(c) == 4 and c not in con_aux):
        salida.append((f"{codigo}05", f"{nombre[codigo]} (general)", naturaleza[codigo]))
    return salida


def puc_semilla() -> list[dict]:
    """Cuentas listas para insertar (sin `empresa_id`): clases, grupos, cuentas (4 dígitos) y auxiliares (6 dígitos)."""
    return [
        {
            "codigo": codigo,
            "nombre": nombre,
            "naturaleza": naturaleza,
            "nivel": _NIVEL_POR_LONGITUD[len(codigo)],
            "codigo_padre": _padre(codigo),
            # Reciben movimientos las cuentas (4 dígitos) y los auxiliares (6 dígitos).
            "acepta_movimientos": len(codigo) >= 4,
        }
        for codigo, nombre, naturaleza in [*_CUENTAS, *_auxiliares_completos()]
    ]
