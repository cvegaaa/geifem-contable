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

_NIVEL_POR_LONGITUD = {1: 1, 2: 2, 4: 3, 6: 4}


def _padre(codigo: str) -> str | None:
    if len(codigo) == 1:
        return None
    return codigo[:1] if len(codigo) == 2 else codigo[: len(codigo) - 2]


def puc_semilla() -> list[dict]:
    """Cuentas listas para insertar (sin `empresa_id`)."""
    return [
        {
            "codigo": codigo,
            "nombre": nombre,
            "naturaleza": naturaleza,
            "nivel": _NIVEL_POR_LONGITUD[len(codigo)],
            "codigo_padre": _padre(codigo),
            # Solo las cuentas (4 dígitos) reciben movimientos.
            "acepta_movimientos": len(codigo) >= 4,
        }
        for codigo, nombre, naturaleza in _CUENTAS
    ]
