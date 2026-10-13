"""Motor de impuestos: IVA, retenciones (ReteFuente, ReteICA, ReteIVA) y autorretención.

Qué se aplica depende de tres perfiles:

- la **empresa** (régimen, responsabilidad de IVA, agente retenedor, autorretenedor);
- el **tercero** (régimen, responsable de IVA, agente retenedor, declarante);
- el **producto** (tipo de IVA y conceptos de retención).

Reglas legales aplicadas (validar con tu contador; las tarifas son parámetros):

- Régimen SIMPLE (art. 911 ET): no está sujeto a retención en la fuente ni
  obligado a practicarla ni a autorretener, salvo pagos laborales y lo
  relacionado con el IVA. Por eso una empresa SIMPLE no sufre ReteFuente/ReteICA
  en sus ventas ni las practica en sus compras, pero sí puede sufrir y practicar
  ReteIVA.
- A un contribuyente SIMPLE (proveedor) tampoco se le practica ReteFuente/ReteICA.
- Una empresa no responsable de IVA no cobra IVA; el IVA que paga en sus
  compras es mayor valor del costo o gasto (no descontable).
- Un autorretenedor especial de renta no sufre ReteFuente de renta en sus ventas:
  se autorretiene (débito anticipo / crédito autorretención por pagar).
- La cuantía mínima de cada concepto se mide en UVT sobre la base acumulada.
"""
from typing import Any

from bson import ObjectId
from fastapi import HTTPException

from core.retenciones import anio_de, valor_uvt
from db import get_db
from core.dinero import redondear

TARIFA_RETEIVA = 15.0  # % del IVA (tarifa general)
TIPOS_CONCEPTO = ("retefuente", "reteica", "reteiva")

# Conceptos sugeridos. SON PUNTO DE PARTIDA: tarifas y bases deben validarse con el
# contador y con el estatuto de rentas del municipio (ReteICA).
CONCEPTOS_SUGERIDOS: list[dict[str, Any]] = [
    {"tipo": "retefuente", "nombre": "Compras generales (declarante)", "tarifa": 2.5, "base_uvt": 27},
    {"tipo": "retefuente", "nombre": "Compras generales (no declarante)", "tarifa": 3.5, "base_uvt": 27},
    {"tipo": "retefuente", "nombre": "Servicios generales (declarante)", "tarifa": 4.0, "tarifa_no_declarante": 6.0, "base_uvt": 4},
    {"tipo": "retefuente", "nombre": "Honorarios y comisiones (persona jurídica)", "tarifa": 11.0, "base_uvt": 0},
    {"tipo": "retefuente", "nombre": "Honorarios y comisiones (persona natural)", "tarifa": 10.0, "base_uvt": 0},
    {"tipo": "retefuente", "nombre": "Arrendamiento de bienes inmuebles", "tarifa": 3.5, "base_uvt": 27},
    {"tipo": "retefuente", "nombre": "Arrendamiento de bienes muebles", "tarifa": 4.0, "base_uvt": 0},
    {"tipo": "retefuente", "nombre": "Transporte de carga", "tarifa": 1.0, "base_uvt": 4},
    {"tipo": "retefuente", "nombre": "Hoteles y restaurantes", "tarifa": 3.5, "base_uvt": 4},
    {"tipo": "reteica", "nombre": "ReteICA (ajusta la tarifa a tu municipio y actividad)", "tarifa": 4.14, "base_uvt": 0},
    {"tipo": "reteiva", "nombre": "ReteIVA general (15% del IVA)", "tarifa": TARIFA_RETEIVA, "base_uvt": 0},
]


def conceptos_sugeridos(empresa_id: str, momento) -> list[dict]:
    return [
        {"empresa_id": empresa_id, "activo": True, "fecha_creacion": momento, "sugerido": True, **c}
        for c in CONCEPTOS_SUGERIDOS
    ]


# ---------------------------------------------------------------------------
# Perfil de la empresa
# ---------------------------------------------------------------------------

def capacidades(empresa: dict) -> dict[str, Any]:
    """Qué impuestos puede cobrar, sufrir y practicar la empresa según su perfil."""
    simple = empresa.get("regimen_tributario") == "SIMPLE"
    responsable_iva = bool(empresa.get("responsable_iva", True))
    agente = bool(empresa.get("agente_retenedor", not simple)) and not simple
    agente_iva = bool(empresa.get("agente_reteiva", not simple)) and responsable_iva
    autorretenedor = bool(empresa.get("autorretenedor_renta", False)) and not simple
    gran = bool(empresa.get("gran_contribuyente", False))
    return {
        "regimen": empresa.get("regimen_tributario", "ORDINARIO"),
        "cobra_iva": responsable_iva,
        "gran_contribuyente": gran,
        "sufre_retefuente": not simple and not autorretenedor,
        "sufre_reteica": not simple,
        "sufre_reteiva": responsable_iva,
        "practica_retefuente": agente,
        "practica_reteica": agente,
        "practica_reteiva": agente_iva,
        "autorretenedor_renta": autorretenedor,
        "tarifa_autorretencion": float(empresa.get("tarifa_autorretencion", 0.8) or 0),
        "tarifa_reteica": float(empresa.get("tarifa_reteica", 0) or 0),
        "notas": _notas(simple, responsable_iva, autorretenedor),
    }


def _notas(simple: bool, responsable_iva: bool, autorretenedor: bool) -> list[str]:
    notas = []
    if simple:
        notas.append(
            "Régimen SIMPLE (art. 911 ET): no te practican retención en la fuente ni la practicas "
            "(salvo pagos laborales). Solo aplica ReteIVA."
        )
    if not responsable_iva:
        notas.append("No eres responsable de IVA: no cobras IVA y el IVA que pagas en compras se suma al costo o gasto.")
    if autorretenedor:
        notas.append("Eres autorretenedor de renta: tus clientes no te retienen renta; tú te autorretienes en cada venta.")
    return notas


async def empresa_y_capacidades(empresa_id: str, s=None) -> tuple[dict, dict]:
    empresa = await get_db().empresas.find_one({"_id": ObjectId(empresa_id)}, session=s) or {}
    return empresa, capacidades(empresa)


async def validar_concepto(empresa_id: str, concepto_id: str | None, tipo: str, campo: str) -> dict | None:
    if not concepto_id:
        return None
    try:
        oid = ObjectId(concepto_id)
    except Exception:
        raise HTTPException(422, f"{campo}: concepto inválido")
    c = await get_db().conceptos_retencion.find_one({"_id": oid, "empresa_id": empresa_id, "activo": {"$ne": False}})
    if not c or c.get("tipo") != tipo:
        raise HTTPException(422, f"{campo}: el concepto no existe o no es de tipo {tipo}")
    return c


# ---------------------------------------------------------------------------
# Retenciones
# ---------------------------------------------------------------------------

def _redondear(v: float) -> float:
    return redondear(v + 1e-9, 2)


def _retener_por_concepto(
    bases: dict[str, tuple[dict, float]], uvt: int, es_declarante: bool, detalle: list[dict], tipo: str
) -> float:
    """Aplica cada concepto a su base acumulada respetando la cuantía mínima en UVT."""
    total = 0.0
    for concepto, base in bases.values():
        tarifa = float(concepto["tarifa"])
        if not es_declarante and concepto.get("tarifa_no_declarante"):
            tarifa = float(concepto["tarifa_no_declarante"])
        minimo = redondear(float(concepto.get("base_uvt") or 0) * uvt, 2)
        fila = {"concepto": concepto["nombre"], "tipo": tipo, "tarifa": tarifa, "base": _redondear(base),
                "base_minima": minimo, "cuenta_pasivo": concepto.get("cuenta_pasivo"),
                "cuenta_favor": concepto.get("cuenta_favor")}
        if base < minimo:
            detalle.append({**fila, "valor": 0.0, "aplica": False,
                            "motivo": f"Base inferior a la cuantía mínima ({concepto.get('base_uvt')} UVT)"})
            continue
        valor = _redondear(base * tarifa / (1000 if tipo == "reteica" else 100))
        total += valor
        detalle.append({**fila, "valor": valor, "aplica": True, "motivo": None})
    return total


def retenciones_compra(
    cap: dict, proveedor: dict, items: list[dict], concepto_reteica: dict | None,
    aplicar_reteiva: bool, iva_total: float, fecha: str,
) -> dict:
    """Retenciones que la empresa practica al pagar una compra.

    `items`: [{subtotal, concepto (dict|None)}] con el concepto de ReteFuente de cada línea.
    """
    uvt = valor_uvt(anio_de(fecha))
    detalle: list[dict] = []
    ret = {"retefuente": 0.0, "reteica": 0.0, "reteiva": 0.0}

    prov_simple = proveedor.get("regimen") == "SIMPLE"
    prov_autorretenedor = bool(proveedor.get("autorretenedor"))
    declarante = proveedor.get("declarante_renta", True) is not False
    subtotal = sum(i["subtotal"] for i in items)

    if cap["practica_retefuente"] and not prov_simple and not prov_autorretenedor:
        bases: dict[str, tuple[dict, float]] = {}
        for it in items:
            c = it.get("concepto")
            if c:
                cid = str(c["_id"])
                bases[cid] = (c, bases.get(cid, (c, 0.0))[1] + it["subtotal"])
        ret["retefuente"] = _retener_por_concepto(bases, uvt, declarante, detalle, "retefuente")
    elif any(i.get("concepto") for i in items):
        motivo = ("el proveedor es del régimen SIMPLE (art. 911 ET)" if prov_simple
                  else "el proveedor es autorretenedor" if prov_autorretenedor
                  else "tu empresa no es agente retenedor")
        detalle.append({"concepto": "ReteFuente", "tipo": "retefuente", "valor": 0.0, "aplica": False,
                        "motivo": f"No aplica: {motivo}"})

    if cap["practica_reteica"] and concepto_reteica and not prov_simple:
        ret["reteica"] = _retener_por_concepto(
            {str(concepto_reteica["_id"]): (concepto_reteica, subtotal)}, uvt, declarante, detalle, "reteica")

    if (cap["practica_reteiva"] and aplicar_reteiva and iva_total > 0
            and proveedor.get("responsable_iva", True) is not False):
        minimos = [float(i["concepto"].get("base_uvt") or 0) * uvt for i in items if i.get("concepto")]
        minimo = min(minimos) if minimos else 0.0
        fila = {"concepto": "ReteIVA", "tipo": "reteiva", "tarifa": TARIFA_RETEIVA, "base": _redondear(iva_total),
                "base_minima": minimo}
        if subtotal < minimo:
            detalle.append({**fila, "valor": 0.0, "aplica": False, "motivo": "Base inferior a la cuantía mínima"})
        else:
            ret["reteiva"] = _redondear(iva_total * TARIFA_RETEIVA / 100)
            detalle.append({**fila, "valor": ret["reteiva"], "aplica": True, "motivo": None})

    ret = {k: _redondear(v) for k, v in ret.items()}
    return {"retenciones": ret, "total": _redondear(sum(ret.values())), "detalle": detalle, "uvt": uvt}


def retenciones_venta(
    cap: dict, cliente: dict | None, items: list[dict], iva_total: float, fecha: str,
) -> dict:
    """Retenciones que le practica el cliente a la empresa (retención a favor).

    `items`: [{subtotal, concepto (dict|None), aplica_reteica (bool)}].
    """
    uvt = valor_uvt(anio_de(fecha))
    detalle: list[dict] = []
    ret = {"retefuente": 0.0, "reteica": 0.0, "reteiva": 0.0}
    cliente = cliente or {}
    es_agente = bool(cliente.get("agente_retenedor") or cliente.get("gran_contribuyente"))
    es_agente_iva = bool(cliente.get("agente_reteiva") or cliente.get("gran_contribuyente"))

    if es_agente and cap["sufre_retefuente"]:
        bases: dict[str, tuple[dict, float]] = {}
        for it in items:
            c = it.get("concepto")
            if c:
                cid = str(c["_id"])
                bases[cid] = (c, bases.get(cid, (c, 0.0))[1] + it["subtotal"])
        ret["retefuente"] = _retener_por_concepto(bases, uvt, True, detalle, "retefuente")

    if es_agente and cap["sufre_reteica"] and cap["tarifa_reteica"] > 0:
        base = sum(i["subtotal"] for i in items if i.get("aplica_reteica", True))
        if base > 0:
            ret["reteica"] = _redondear(base * cap["tarifa_reteica"] / 1000)
            detalle.append({"concepto": "ReteICA", "tipo": "reteica", "tarifa": cap["tarifa_reteica"],
                            "base": _redondear(base), "valor": ret["reteica"], "aplica": True, "motivo": None})

    if es_agente_iva and cap["sufre_reteiva"] and iva_total > 0:
        ret["reteiva"] = _redondear(iva_total * TARIFA_RETEIVA / 100)
        detalle.append({"concepto": "ReteIVA", "tipo": "reteiva", "tarifa": TARIFA_RETEIVA,
                        "base": _redondear(iva_total), "valor": ret["reteiva"], "aplica": True, "motivo": None})

    ret = {k: _redondear(v) for k, v in ret.items()}
    return {"retenciones": ret, "total": _redondear(sum(ret.values())), "detalle": detalle, "uvt": uvt}


def autorretencion(cap: dict, subtotal: float) -> float:
    """Autorretención especial de renta sobre el ingreso (solo autorretenedores)."""
    if not cap["autorretenedor_renta"]:
        return 0.0
    return _redondear(subtotal * cap["tarifa_autorretencion"] / 100)


def lineas_retencion(detalle: list[dict], params: dict[str, str], sentido: str, factor: float = 1.0) -> list[tuple[str, float]]:
    """Cuenta y valor de cada retención aplicada.

    `sentido`: "practicada" (la retienes tú: pasivo) o "sufrida" (te la retienen: activo a favor).
    Cada concepto puede tener su propia cuenta; si no, se usa la de los parámetros contables.
    """
    salida: list[tuple[str, float]] = []
    for d in detalle:
        if not d.get("aplica") or not d.get("valor"):
            continue
        if sentido == "practicada":
            cuenta = d.get("cuenta_pasivo") or params[d["tipo"]]
        else:
            cuenta = d.get("cuenta_favor") or params[f"{d['tipo']}_favor"]
        salida.append((cuenta, _redondear(d["valor"] * factor)))
    return salida


def prorratear_retenciones(detalle: list[dict], factor: float) -> tuple[list[dict], dict[str, float], float]:
    """Parte proporcional de las retenciones de una factura (para notas crédito/débito)."""
    filas, por_tipo = [], {"retefuente": 0.0, "reteica": 0.0, "reteiva": 0.0}
    for d in detalle:
        if not d.get("aplica") or not d.get("valor"):
            continue
        valor = _redondear(d["valor"] * factor)
        filas.append({**d, "valor": valor})
        por_tipo[d["tipo"]] += valor
    por_tipo = {k: _redondear(v) for k, v in por_tipo.items()}
    return filas, por_tipo, _redondear(sum(por_tipo.values()))
