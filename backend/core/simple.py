"""Régimen Simple de Tributación (SIMPLE): tarifas consolidadas por grupo de actividad y por tramo de ingresos.

Las tarifas son parámetros editables por empresa (Configuración › Tarifas del régimen SIMPLE). Los valores por
defecto son de referencia (art. 908 ET, Ley 2277 de 2022) y deben verificarse con el contador cada año.
"""
from copy import deepcopy

from fastapi import HTTPException

from db import get_db

# grupo -> (descripción, [(hasta UVT, tarifa %)])
GRUPOS_DEFECTO: dict[str, tuple[str, list[tuple[int, float]]]] = {
    "1": ("Tiendas pequeñas, mini-mercados, micro-mercados y peluquería",
          [(6000, 1.2), (15000, 2.8), (30000, 8.1), (100000, 11.6)]),
    "2": ("Comercio al por mayor y detal, servicios técnicos y mecánicos, industria y demás actividades",
          [(6000, 1.6), (15000, 2.0), (30000, 3.5), (100000, 4.5)]),
    "3": ("Servicios profesionales, de consultoría y científicos (predomina el factor intelectual)",
          [(6000, 5.9), (15000, 7.3), (30000, 12.0), (100000, 14.5)]),
    "4": ("Expendio de comidas y bebidas, y transporte",
          [(6000, 3.4), (15000, 3.8), (30000, 5.5), (100000, 7.0)]),
    "5": ("Educación y atención de la salud humana y asistencia social",
          [(6000, 3.7), (15000, 4.3), (30000, 5.7), (100000, 6.6)]),
}


def por_defecto() -> dict:
    return {"verificado": False,
            "grupos": {g: {"nombre": n, "tramos": [{"hasta_uvt": h, "tarifa": t} for h, t in tramos]}
                       for g, (n, tramos) in GRUPOS_DEFECTO.items()}}


async def obtener(empresa_id: str) -> dict:
    doc = await get_db().tarifas_simple.find_one({"empresa_id": empresa_id})
    base = por_defecto()
    if not doc:
        return base
    base["verificado"] = bool(doc.get("verificado"))
    for g, v in (doc.get("grupos") or {}).items():
        if g in base["grupos"] and v.get("tramos"):
            base["grupos"][g]["tramos"] = deepcopy(v["tramos"])
    return base


def validar(grupos: dict) -> None:
    for g, v in grupos.items():
        if g not in GRUPOS_DEFECTO:
            raise HTTPException(422, f"Grupo desconocido: {g}")
        tramos = v.get("tramos") or []
        if not tramos:
            raise HTTPException(422, f"El grupo {g} necesita al menos un tramo")
        previo = 0
        for t in tramos:
            if not (0 <= float(t.get("tarifa", -1)) <= 100):
                raise HTTPException(422, f"Grupo {g}: la tarifa debe estar entre 0 y 100")
            if float(t.get("hasta_uvt", 0)) <= previo:
                raise HTTPException(422, f"Grupo {g}: los tramos deben ir en orden creciente de UVT")
            previo = float(t["hasta_uvt"])


def tarifa_para(grupo: dict, ingresos: float, uvt: float) -> tuple[float, float]:
    """(tarifa %, ingresos en UVT) del tramo en que caen los ingresos brutos acumulados."""
    en_uvt = ingresos / uvt if uvt else 0.0
    tramos = grupo["tramos"]
    for t in tramos:
        if en_uvt <= float(t["hasta_uvt"]):
            return float(t["tarifa"]), en_uvt
    return float(tramos[-1]["tarifa"]), en_uvt   # excede el tope SIMPLE: se muestra con la última tarifa
