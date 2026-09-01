"""Semillas mínimas del Plan Único de Cuentas.

NOTA: Es solo un extracto para arrancar. El PUC completo se carga
desde `configuracion/plan-cuentas` por empresa.
"""
from typing import Literal

Regimen = Literal["SIMPLE", "COMUN"]

SEMILLA_COMUN = [
    {"codigo": "1", "nombre": "ACTIVO", "naturaleza": "debito", "nivel": 1},
    {"codigo": "11", "nombre": "DISPONIBLE", "naturaleza": "debito", "nivel": 2},
    {"codigo": "1105", "nombre": "Caja", "naturaleza": "debito", "nivel": 4},
    {"codigo": "1110", "nombre": "Bancos", "naturaleza": "debito", "nivel": 4},
    {"codigo": "13", "nombre": "DEUDORES", "naturaleza": "debito", "nivel": 2},
    {"codigo": "1305", "nombre": "Clientes", "naturaleza": "debito", "nivel": 4},
    {"codigo": "14", "nombre": "INVENTARIOS", "naturaleza": "debito", "nivel": 2},
    {"codigo": "1435", "nombre": "Mercancías no fabricadas", "naturaleza": "debito", "nivel": 4},
    {"codigo": "2", "nombre": "PASIVO", "naturaleza": "credito", "nivel": 1},
    {"codigo": "2205", "nombre": "Proveedores", "naturaleza": "credito", "nivel": 4},
    {"codigo": "2408", "nombre": "IVA por pagar", "naturaleza": "credito", "nivel": 4},
    {"codigo": "3", "nombre": "PATRIMONIO", "naturaleza": "credito", "nivel": 1},
    {"codigo": "4", "nombre": "INGRESOS", "naturaleza": "credito", "nivel": 1},
    {"codigo": "4135", "nombre": "Comercio al por mayor y menor", "naturaleza": "credito", "nivel": 4},
    {"codigo": "5", "nombre": "GASTOS", "naturaleza": "debito", "nivel": 1},
    {"codigo": "6", "nombre": "COSTOS DE VENTAS", "naturaleza": "debito", "nivel": 1},
    {"codigo": "6135", "nombre": "Costo mercancía vendida", "naturaleza": "debito", "nivel": 4},
]

# Régimen SIMPLE: se omite IVA por pagar como cuenta operativa habitual.
SEMILLA_SIMPLE = [c for c in SEMILLA_COMUN if c["codigo"] != "2408"]


def puc_semilla(regimen: Regimen) -> list[dict]:
    return SEMILLA_SIMPLE if regimen == "SIMPLE" else SEMILLA_COMUN
