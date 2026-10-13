"""Nómina: empleados, novedades, liquidación por periodo, pagos, prestaciones, PILA,
liquidación de contrato y nómina electrónica (paquete mensual consolidado).

Cada transacción deja su asiento contable (cuentas en Parámetros contables › Nómina):

- Liquidación de un periodo: gastos de personal contra salarios por pagar, aportes,
  retenciones y provisiones de prestaciones.
- Pago de nómina: salarios por pagar contra caja o banco.
- Pago de prima, cesantías, intereses o seguridad social: obligación contra caja o banco.
- Liquidación de contrato: cancela las provisiones del empleado y reconoce lo que falte o sobre.

La nómina puede pagarse mensual o quincenal; la nómina electrónica se consolida por mes.
"""
from collections import defaultdict
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api._crud import crud_router
from api.tesoreria import _lineas_tesoreria, _validar_cuenta
from core import nomina as motor
from core import parametros
from core.auth.dependencies import get_empresa_activa, require_permiso
from core.dian.nomina_pt import construir_documento_soporte, get_cliente_nomina
from core.documentos import (
    NO_ANULADO,
    Linea,
    ahora,
    auditar,
    borrar_asientos,
    cargar_editable,
    en_transaccion,
    formatear_numero,
    marca_anulacion,
    oid,
    registrar_asientos,
    serializar,
    siguiente_consecutivo,
)
from db import get_db
from core.dinero import redondear

router = APIRouter()
nom = APIRouter(prefix="/api/nomina", tags=["nomina"])

TIPOS_CONTRATO = ("indefinido", "fijo", "obra_labor", "aprendizaje", "practicas")
OBLIGACIONES = {"prima": "nomina_prima", "cesantias": "nomina_cesantias",
                "intereses": "nomina_intereses", "vacaciones": "nomina_vacaciones"}


class Anulacion(BaseModel):
    motivo: str | None = None


async def _parametros(empresa_id: str, anio: int, s=None) -> dict:
    doc = await get_db().nomina_parametros.find_one({"empresa_id": empresa_id, "anio": anio}, session=s)
    return motor.parametros_anio(anio, (doc or {}).get("valores"))


def _fecha_valida(valor, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise HTTPException(422, f"{campo}: fecha inválida (usa AAAA-MM-DD)")


# ---------------------------------------------------------------------------
# Empleados y novedades (catálogos)
# ---------------------------------------------------------------------------

async def _validar_empleado(payload: dict, empresa_id: str) -> None:
    for campo, nombre in (("primer_nombre", "primer nombre"), ("primer_apellido", "primer apellido"),
                          ("numero_documento", "número de documento"), ("fecha_ingreso", "fecha de ingreso")):
        if not str(payload.get(campo) or "").strip():
            raise HTTPException(422, f"Falta el {nombre}")
    ingreso = _fecha_valida(payload["fecha_ingreso"], "Fecha de ingreso")
    try:
        salario = float(payload.get("salario_basico") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "Salario inválido")
    if salario <= 0:
        raise HTTPException(422, "Indica el salario básico mensual")
    p = await _parametros(empresa_id, max(ingreso.year, date.today().year))
    if salario < p["smmlv"] and not payload.get("tiempo_parcial"):
        raise HTTPException(
            422, f"El salario no puede ser menor al mínimo (${p['smmlv']:,.0f}). Si es tiempo parcial, márcalo.")
    payload["salario_basico"] = salario
    payload.setdefault("frecuencia_pago", "mensual")
    if payload["frecuencia_pago"] not in ("mensual", "quincenal"):
        raise HTTPException(422, "La frecuencia de pago debe ser mensual o quincenal")
    payload.setdefault("riesgo_arl", "I")
    if payload["riesgo_arl"] not in p["arl"]:
        raise HTTPException(422, "Nivel de riesgo ARL inválido (I a V)")
    payload.setdefault("tipo_contrato", "indefinido")
    if payload["tipo_contrato"] not in TIPOS_CONTRATO:
        raise HTTPException(422, "Tipo de contrato inválido")
    # Cada empleado lleva sus cuentas de gasto (centro de costo contable); si no se eligen, las de respaldo de la empresa.
    respaldo = await parametros.obtener(empresa_id)
    for campo, param in CUENTAS_EMPLEADO.items():
        if not payload.get(campo):
            payload[campo] = respaldo[param]
    await parametros.validar_codigos(empresa_id, {campo: payload.get(campo) for campo in CUENTAS_EMPLEADO})


# campo del empleado -> parámetro contable de respaldo
CUENTAS_EMPLEADO = {
    "cuenta_gasto_salarios": "nomina_gasto_salarios",
    "cuenta_gasto_horas_extra": "nomina_gasto_horas_extra",
    "cuenta_gasto_aux_transporte": "nomina_gasto_aux_transporte",
    "cuenta_gasto_seguridad_social": "nomina_gasto_seguridad_social",
    "cuenta_gasto_parafiscales": "nomina_gasto_parafiscales",
    "cuenta_gasto_prestaciones": "nomina_gasto_prestaciones",
}


def _cuenta_emp(emp: dict | None, campo: str, p: dict) -> str:
    """Cuenta de gasto del empleado o, si no la tiene, la de respaldo de la empresa."""
    return (emp or {}).get(campo) or p[CUENTAS_EMPLEADO[campo]]


async def _validar_novedad(payload: dict, empresa_id: str) -> None:
    tipo = payload.get("tipo")
    if tipo not in motor.TIPOS_NOVEDAD:
        raise HTTPException(422, "Tipo de novedad inválido")
    emp = await get_db().empleados.find_one(
        {"_id": oid(payload.get("empleado_id"), "empleado_id"), "empresa_id": empresa_id})
    if not emp:
        raise HTTPException(422, "Empleado no encontrado")
    payload["empleado_nombre"] = motor.nombre_empleado(emp)
    _fecha_valida(payload.get("fecha_inicio"), "Fecha")
    por_cantidad = tipo in motor.TIPOS_HORAS or tipo in motor.TIPOS_DIAS
    campo = "cantidad" if por_cantidad else "valor"
    try:
        valor = float(payload.get(campo) or 0)
    except (TypeError, ValueError):
        valor = 0
    if valor <= 0:
        raise HTTPException(422, "Indica la cantidad (horas o días)" if por_cantidad else "Indica el valor")
    payload[campo] = valor


router.include_router(crud_router(
    prefix="/api/nomina/empleados", coleccion="empleados", modulo_permiso="nomina", tags=["nomina:empleados"],
    protegidos=("fecha_retiro", "estado", "causa_retiro"), validar=_validar_empleado))
router.include_router(crud_router(
    prefix="/api/nomina/novedades", coleccion="nomina_novedades", modulo_permiso="nomina",
    tags=["nomina:novedades"], validar=_validar_novedad))


# ---------------------------------------------------------------------------
# Parámetros por año
# ---------------------------------------------------------------------------

class ParametrosNomina(BaseModel):
    valores: dict


@nom.get("/parametros")
async def ver_parametros(
    anio: int = Query(default_factory=lambda: date.today().year),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("nomina", "leer")),
):
    return await _parametros(empresa_id, anio)


@nom.put("/parametros")
async def guardar_parametros(
    payload: ParametrosNomina,
    anio: int = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "editar")),
):
    desconocidos = set(payload.valores) - set(motor.PARAMETROS_2026) - {"verificado"}
    if desconocidos:
        raise HTTPException(422, f"Parámetros desconocidos: {', '.join(sorted(desconocidos))}")
    valores = {**payload.valores}
    valores["verificado"] = True  # quien los guarda los está confirmando
    await get_db().nomina_parametros.update_one(
        {"empresa_id": empresa_id, "anio": anio},
        {"$set": {"valores": valores, "actualizado_por": usuario["id"], "fecha_actualizacion": ahora()}},
        upsert=True,
    )
    return await _parametros(empresa_id, anio)


# ---------------------------------------------------------------------------
# Periodos de nómina (mensual o quincenal)
# ---------------------------------------------------------------------------

class PeriodoCrear(BaseModel):
    anio: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)
    tipo: Literal["mensual", "quincena1", "quincena2"]
    fecha_pago: str | None = None


PERIODO = "nomina_periodo"


async def _construir_periodo(empresa_id: str, payload: PeriodoCrear, s, excluir_id=None) -> dict:
    db = get_db()
    duplicado = {"empresa_id": empresa_id, "anio": payload.anio, "mes": payload.mes, "tipo": payload.tipo, **NO_ANULADO}
    if excluir_id is not None:
        duplicado["_id"] = {"$ne": excluir_id}
    if await db.nomina_periodos.find_one(duplicado, session=s):
        raise HTTPException(409, "Ya existe una liquidación de ese periodo: edítala o anúlala")

    inicio, fin, dias = motor.rango_periodo(payload.anio, payload.mes, payload.tipo)
    p = await _parametros(empresa_id, payload.anio, s)
    frecuencia = "mensual" if payload.tipo == "mensual" else "quincenal"
    empleados = [
        {**e, "id": str(e["_id"])}
        async for e in db.empleados.find(
            {"empresa_id": empresa_id, "activo": {"$ne": False}, "frecuencia_pago": frecuencia}, session=s)
        if e["fecha_ingreso"] <= fin.isoformat() and (not e.get("fecha_retiro") or e["fecha_retiro"] >= inicio.isoformat())
    ]
    if not empleados:
        raise HTTPException(409, f"No hay empleados con pago {frecuencia} para liquidar en ese periodo")

    previo: dict[str, dict] = {}
    if payload.tipo == "quincena2":
        q1 = await db.nomina_periodos.find_one(
            {"empresa_id": empresa_id, "anio": payload.anio, "mes": payload.mes, "tipo": "quincena1", **NO_ANULADO},
            session=s)
        previo = {l["empleado_id"]: l for l in (q1 or {}).get("lineas", [])}

    lineas = []
    for e in empleados:
        novs = [
            n async for n in db.nomina_novedades.find({
                "empresa_id": empresa_id, "empleado_id": e["id"], "activo": {"$ne": False},
                "fecha_inicio": {"$gte": inicio.isoformat(), "$lte": fin.isoformat()}}, session=s)
        ]
        linea = motor.liquidar_empleado(e, novs, inicio, fin, dias, p, previo.get(e["id"]),
                                        es_ultimo_periodo_mes=payload.tipo != "quincena1")
        linea["novedades_ids"] = [str(n["_id"]) for n in novs]
        lineas.append(linea)
    return {
        "anio": payload.anio, "mes": payload.mes, "tipo": payload.tipo,
        "fecha_inicio": inicio.isoformat(), "fecha_fin": fin.isoformat(),
        "fecha_pago_prevista": payload.fecha_pago, "lineas": lineas, "totales": motor.totales_periodo(lineas),
        "parametros_verificados": bool(p["verificado"]), "estado": "liquidado", "pagado": False,
    }


async def _aplicar_periodo(empresa_id: str, pid: str, doc: dict, s) -> None:
    db = get_db()
    p = await parametros.obtener(empresa_id, s)
    t = doc["totales"]
    # El gasto de cada empleado se contabiliza en sus propias cuentas (puede haber áreas o centros distintos).
    gastos: dict[str, float] = {}
    empleados = {str(e["_id"]): e async for e in db.empleados.find(
        {"_id": {"$in": [oid(l["empleado_id"]) for l in doc["lineas"]]}, "empresa_id": empresa_id}, session=s)}
    for l in doc["lineas"]:
        tl = motor.totales_periodo([l])
        emp = empleados.get(l["empleado_id"])
        for campo, valor in (
            ("cuenta_gasto_salarios", tl["sueldos"]), ("cuenta_gasto_horas_extra", tl["horas_extra"]),
            ("cuenta_gasto_aux_transporte", tl["aux_transporte"]),
            ("cuenta_gasto_seguridad_social", tl["seguridad_social_empleador"]),
            ("cuenta_gasto_parafiscales", tl["parafiscales"]),
            ("cuenta_gasto_prestaciones", tl["cesantias"] + tl["intereses"] + tl["prima"] + tl["vacaciones"]),
        ):
            cuenta = _cuenta_emp(emp, campo, p)
            gastos[cuenta] = gastos.get(cuenta, 0.0) + valor
    lineas = [Linea(codigo=c, debito=redondear(v, 2)) for c, v in gastos.items()] + [
        Linea(codigo=p["nomina_eps_por_cobrar"], debito=t["a_cargo_eps_arl"], descripcion="Incapacidades por recobrar"),
        Linea(codigo=p["nomina_salarios_por_pagar"], credito=t["neto_pagar"]),
        Linea(codigo=p["nomina_aportes_empleado"], credito=t["salud_empleado"] + t["pension_empleado"] + t["fsp"]),
        Linea(codigo=p["nomina_retefuente"], credito=t["retefuente"]),
        Linea(codigo=p["nomina_prestamos_empleados"], credito=t["prestamos"]),
        Linea(codigo=p["nomina_otros_descuentos"], credito=t["otras_deducciones"]),
        Linea(codigo=p["nomina_aportes_empleador"], credito=t["seguridad_social_empleador"] + t["parafiscales"]),
        Linea(codigo=p["nomina_cesantias"], credito=t["cesantias"]),
        Linea(codigo=p["nomina_intereses"], credito=t["intereses"]),
        Linea(codigo=p["nomina_prima"], credito=t["prima"]),
        Linea(codigo=p["nomina_vacaciones"], credito=t["vacaciones"]),
    ]
    await registrar_asientos(empresa_id, PERIODO, pid, doc["numero"], doc["fecha_fin"], lineas, s)
    entradas = [
        {"empresa_id": empresa_id, "empleado_id": l["empleado_id"], "tipo": tipo, "valor": l["provisiones"][tipo],
         "fecha": doc["fecha_fin"], "documento_tipo": PERIODO, "documento_id": pid, "fecha_creacion": ahora()}
        for l in doc["lineas"] for tipo in OBLIGACIONES if l["provisiones"][tipo]
    ]
    if entradas:
        await db.nomina_obligaciones.insert_many(entradas, session=s)


async def _revertir_documento(empresa_id: str, tipo: str, did: str, s) -> None:
    await borrar_asientos(empresa_id, tipo, did, s)
    await get_db().nomina_obligaciones.delete_many(
        {"empresa_id": empresa_id, "documento_tipo": tipo, "documento_id": did}, session=s)


async def _validar_periodo_modificable(empresa_id: str, doc: dict, s) -> None:
    if doc.get("pagado"):
        raise HTTPException(409, "El periodo ya fue pagado: anula primero el pago")
    if await get_db().nomina_electronica.find_one(
        {"empresa_id": empresa_id, "anio": doc["anio"], "mes": doc["mes"], "estado": {"$ne": "borrador"}}, session=s
    ):
        raise HTTPException(409, "La nómina electrónica de ese mes ya fue transmitida a la DIAN")


@nom.get("/periodos")
async def listar_periodos(
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    cursor = get_db().nomina_periodos.find({"empresa_id": empresa_id}, {"lineas": 0}).sort(
        [("fecha_inicio", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@nom.get("/periodos/{pid}")
async def obtener_periodo(
    pid: str, empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    doc = await get_db().nomina_periodos.find_one({"_id": oid(pid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Periodo no encontrado")
    return serializar(doc)


@nom.post("/periodos", status_code=201)
async def crear_periodo(
    payload: PeriodoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "crear")),
):
    db = get_db()

    async def _tx(s):
        doc = await _construir_periodo(empresa_id, payload, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "nomina_periodo", s)
        doc.update({"empresa_id": empresa_id, "prefijo": "NOM", "consecutivo": consecutivo,
                    "numero": formatear_numero("NOM", consecutivo), "creado_por": usuario["id"],
                    "fecha_creacion": ahora()})
        res = await db.nomina_periodos.insert_one(doc, session=s)
        pid = str(res.inserted_id)
        await _aplicar_periodo(empresa_id, pid, doc, s)
        await auditar(empresa_id, PERIODO, pid, doc["numero"], usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.nomina_periodos.find_one({"_id": nuevo}))


@nom.put("/periodos/{pid}")
async def recalcular_periodo(
    pid: str,
    payload: PeriodoCrear,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "editar")),
):
    """Recalcula la liquidación con los empleados, novedades y parámetros actuales."""
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("nomina_periodos", empresa_id, pid, s)
        await _validar_periodo_modificable(empresa_id, existente, s)
        if (payload.anio, payload.mes, payload.tipo) != (existente["anio"], existente["mes"], existente["tipo"]):
            raise HTTPException(409, "No se puede cambiar el periodo de una liquidación numerada")
        await _revertir_documento(empresa_id, PERIODO, pid, s)
        doc = await _construir_periodo(empresa_id, payload, s, excluir_id=existente["_id"])
        for campo in ("empresa_id", "prefijo", "consecutivo", "numero", "creado_por", "fecha_creacion"):
            doc[campo] = existente[campo]
        doc.update({"editado_por": usuario["id"], "fecha_actualizacion": ahora()})
        await db.nomina_periodos.replace_one({"_id": existente["_id"]}, doc, session=s)
        await _aplicar_periodo(empresa_id, pid, doc, s)
        await auditar(empresa_id, PERIODO, pid, doc["numero"], usuario["id"], "editado", s)

    await en_transaccion(_tx)
    return serializar(await db.nomina_periodos.find_one({"_id": oid(pid)}))


@nom.post("/periodos/{pid}/anular")
async def anular_periodo(
    pid: str, payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        existente = await cargar_editable("nomina_periodos", empresa_id, pid, s)
        await _validar_periodo_modificable(empresa_id, existente, s)
        await _revertir_documento(empresa_id, PERIODO, pid, s)
        await db.nomina_periodos.update_one(
            {"_id": existente["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, PERIODO, pid, existente["numero"], usuario["id"], "anulado", s,
                      {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.nomina_periodos.find_one({"_id": oid(pid)}))


# ---------------------------------------------------------------------------
# Pago de nómina (salarios por pagar -> caja o banco)
# ---------------------------------------------------------------------------

class PagoNomina(BaseModel):
    documento_tipo: Literal["periodo", "liquidacion_final"]
    documento_id: str
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    fecha: str


PAGO = "pago_nomina"


async def _movimiento_efectivo(
    empresa_id: str, cuenta_tipo: str, cuenta_id: str, fecha: str, valor: float, concepto: str, numero: str,
    doc_tipo: str, doc_id: str, usuario_id: str, s,
) -> dict:
    from api.tesoreria import cuenta_contable_de

    cuenta = await _validar_cuenta(get_db(), empresa_id, cuenta_tipo, cuenta_id, s)
    mov = {
        "empresa_id": empresa_id, "cuenta_tipo": cuenta_tipo, "cuenta_id": cuenta_id,
        "cuenta_nombre": cuenta.get("nombre", ""),
        "cuenta_contable": await cuenta_contable_de(empresa_id, cuenta_tipo, cuenta, s),
        "tipo": "egreso", "fecha": fecha, "valor": valor, "concepto": concepto, "numero": numero, "referencia": numero,
        "origen": "nomina", "estado": "registrado", "documento_tipo": doc_tipo, "documento_id": doc_id,
        "creado_por": usuario_id, "fecha_creacion": ahora(),
    }
    await get_db().movimientos_tesoreria.insert_one(mov, session=s)
    return mov


@nom.post("/pagos", status_code=201)
async def pagar_nomina(
    payload: PagoNomina,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "crear")),
):
    db = get_db()
    coleccion = "nomina_periodos" if payload.documento_tipo == "periodo" else "nomina_liquidaciones_finales"

    async def _tx(s):
        doc = await cargar_editable(coleccion, empresa_id, payload.documento_id, s)
        if doc.get("pagado"):
            raise HTTPException(409, "Este documento ya fue pagado")
        valor = doc["totales"]["neto_pagar"] if payload.documento_tipo == "periodo" else doc["neto_pagar"]
        if valor <= 0:
            raise HTTPException(409, "No hay valor por pagar")
        p = await parametros.obtener(empresa_id, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "pago_nomina", s)
        numero = formatear_numero("PN", consecutivo)
        pago = {"empresa_id": empresa_id, "prefijo": "PN", "consecutivo": consecutivo, "numero": numero,
                "documento_tipo": payload.documento_tipo, "documento_id": payload.documento_id,
                "documento_numero": doc["numero"], "valor": valor, "fecha": payload.fecha,
                "cuenta_tipo": payload.cuenta_tipo, "cuenta_id": payload.cuenta_id, "estado": "registrado",
                "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.nomina_pagos.insert_one(pago, session=s)
        pid = str(res.inserted_id)
        mov = await _movimiento_efectivo(empresa_id, payload.cuenta_tipo, payload.cuenta_id, payload.fecha, valor,
                                         f"Pago nómina {doc['numero']}", numero, PAGO, pid, usuario["id"], s)
        await registrar_asientos(empresa_id, PAGO, pid, numero, payload.fecha,
                                 _lineas_tesoreria(mov, p["nomina_salarios_por_pagar"]), s)
        await db[coleccion].update_one(
            {"_id": doc["_id"]}, {"$set": {"pagado": True, "pago_id": pid, "fecha_pago": payload.fecha}}, session=s)
        await auditar(empresa_id, PAGO, pid, numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.nomina_pagos.find_one({"_id": nuevo}))


@nom.get("/pagos")
async def listar_pagos_nomina(
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    cursor = get_db().nomina_pagos.find({"empresa_id": empresa_id}).sort([("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@nom.post("/pagos/{pid}/anular")
async def anular_pago_nomina(
    pid: str, payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        pago = await cargar_editable("nomina_pagos", empresa_id, pid, s)
        if await db.nomina_electronica.find_one(
            {"empresa_id": empresa_id, "estado": {"$ne": "borrador"}, "periodos": pago["documento_numero"]}, session=s
        ):
            raise HTTPException(409, "La nómina electrónica de ese pago ya fue transmitida")
        mov = await db.movimientos_tesoreria.find_one(
            {"empresa_id": empresa_id, "documento_tipo": PAGO, "documento_id": pid}, session=s)
        if mov and mov.get("conciliado"):
            raise HTTPException(409, "El pago ya está conciliado con el extracto bancario")
        await db.movimientos_tesoreria.delete_many(
            {"empresa_id": empresa_id, "documento_tipo": PAGO, "documento_id": pid}, session=s)
        await borrar_asientos(empresa_id, PAGO, pid, s)
        coleccion = "nomina_periodos" if pago["documento_tipo"] == "periodo" else "nomina_liquidaciones_finales"
        await db[coleccion].update_one(
            {"_id": oid(pago["documento_id"])}, {"$set": {"pagado": False}, "$unset": {"pago_id": "", "fecha_pago": ""}},
            session=s)
        await db.nomina_pagos.update_one(
            {"_id": pago["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, PAGO, pid, pago["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.nomina_pagos.find_one({"_id": oid(pid)}))


# ---------------------------------------------------------------------------
# Prestaciones sociales y seguridad social (PILA)
# ---------------------------------------------------------------------------

async def _saldos_obligaciones(empresa_id: str, tipo: str, s=None) -> dict[str, float]:
    saldos: dict[str, float] = defaultdict(float)
    async for e in get_db().nomina_obligaciones.find({"empresa_id": empresa_id, "tipo": tipo}, session=s):
        saldos[e["empleado_id"]] += float(e["valor"])
    return {k: redondear(v, 2) for k, v in saldos.items()}


async def _nombres_empleados(empresa_id: str) -> dict[str, dict]:
    return {
        str(e["_id"]): {"nombre": motor.nombre_empleado(e), "documento": e.get("numero_documento", "")}
        async for e in get_db().empleados.find({"empresa_id": empresa_id})
    }


@nom.get("/obligaciones")
async def ver_obligaciones(
    tipo: Literal["prima", "cesantias", "intereses", "vacaciones"],
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    """Saldo acumulado por empleado de una prestación (provisionado menos pagado)."""
    saldos = await _saldos_obligaciones(empresa_id, tipo)
    nombres = await _nombres_empleados(empresa_id)
    filas = [{"empleado_id": k, **nombres.get(k, {"nombre": "—", "documento": ""}), "saldo": v}
             for k, v in saldos.items() if abs(v) > 0.5]
    filas.sort(key=lambda f: f["nombre"])
    return {"tipo": tipo, "filas": filas, "total": redondear(sum(f["saldo"] for f in filas), 2)}


async def _resumen_pila(empresa_id: str, anio: int, mes: int) -> dict:
    db = get_db()
    acc: dict[str, dict] = {}
    async for p in db.nomina_periodos.find({"empresa_id": empresa_id, "anio": anio, "mes": mes, **NO_ANULADO}):
        for l in p["lineas"]:
            f = acc.setdefault(l["empleado_id"], {
                "empleado_id": l["empleado_id"], "nombre": l["nombre"], "documento": l["documento"], "dias": 0, "ibc": 0,
                "salud_empleado": 0, "pension_empleado": 0, "fsp": 0, "salud_empleador": 0, "pension_empleador": 0,
                "arl": 0, "caja": 0, "sena": 0, "icbf": 0})
            f["dias"] += l["dias_activos"]
            f["ibc"] += l["ibc"]
            f["salud_empleado"] += l["deducciones"]["salud"]
            f["pension_empleado"] += l["deducciones"]["pension"]
            f["fsp"] += l["deducciones"]["fsp"]
            for k in ("salud", "pension", "arl", "caja", "sena", "icbf"):
                f[k if k in ("arl", "caja", "sena", "icbf") else f"{k}_empleador"] += l["aportes_empleador"][k]
    filas = list(acc.values())
    claves = ("ibc", "salud_empleado", "pension_empleado", "fsp", "salud_empleador", "pension_empleador",
              "arl", "caja", "sena", "icbf")
    totales = {k: redondear(sum(f[k] for f in filas)) for k in claves}
    aportes_empleado = totales["salud_empleado"] + totales["pension_empleado"] + totales["fsp"]
    aportes_empleador = (totales["salud_empleador"] + totales["pension_empleador"] + totales["arl"]
                         + totales["caja"] + totales["sena"] + totales["icbf"])
    pagado = 0.0
    async for pg in db.nomina_pagos_obligaciones.find(
        {"empresa_id": empresa_id, "tipo": "seguridad_social", "anio": anio, "mes": mes, **NO_ANULADO}
    ):
        pagado += pg["valor"]
    total = aportes_empleado + aportes_empleador
    return {"anio": anio, "mes": mes, "filas": filas, "totales": totales, "aportes_empleado": aportes_empleado,
            "aportes_empleador": aportes_empleador, "total": total, "pagado": redondear(pagado, 0),
            "pendiente": redondear(total - pagado, 0)}


@nom.get("/pila")
async def ver_pila(
    anio: int, mes: int = Query(ge=1, le=12),
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    """Soporte para la planilla PILA: aportes por empleado del mes (no es el archivo plano del operador)."""
    return await _resumen_pila(empresa_id, anio, mes)


class LineaObligacion(BaseModel):
    empleado_id: str
    valor: float = Field(gt=0)


class PagoObligacion(BaseModel):
    tipo: Literal["prima", "cesantias", "intereses", "vacaciones", "seguridad_social"]
    fecha: str
    cuenta_tipo: Literal["caja", "banco"]
    cuenta_id: str
    anio: int | None = None
    mes: int | None = Field(default=None, ge=1, le=12)
    lineas: list[LineaObligacion] = Field(default_factory=list)
    valor: float | None = None  # solo seguridad social (por defecto, todo lo pendiente)


OBLIG = "pago_obligacion"


@nom.post("/pagos-obligaciones", status_code=201)
async def pagar_obligacion(
    payload: PagoObligacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "crear")),
):
    """Paga prima, cesantías, intereses, vacaciones o seguridad social contra caja o banco."""
    db = get_db()

    async def _tx(s):
        p = await parametros.obtener(empresa_id, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "pago_obligacion", s)
        numero = formatear_numero("PO", consecutivo)
        debitos: list[Linea] = []
        ledger: list[dict] = []
        if payload.tipo == "seguridad_social":
            if not payload.anio or not payload.mes:
                raise HTTPException(422, "Indica el año y el mes de los aportes")
            pila = await _resumen_pila(empresa_id, payload.anio, payload.mes)
            if pila["pendiente"] <= 0:
                raise HTTPException(409, "No hay aportes pendientes de pago en ese mes")
            valor = float(payload.valor or pila["pendiente"])
            if valor > pila["pendiente"] + 1:
                raise HTTPException(409, f"El valor supera lo pendiente (${pila['pendiente']:,.0f})")
            parte_empleado = redondear(valor * pila["aportes_empleado"] / pila["total"], 0)
            debitos = [Linea(codigo=p["nomina_aportes_empleado"], debito=parte_empleado, descripcion="Aportes del empleado"),
                       Linea(codigo=p["nomina_aportes_empleador"], debito=valor - parte_empleado, descripcion="Aportes del empleador")]
            concepto = f"Seguridad social {payload.anio}-{payload.mes:02d}"
        else:
            if not payload.lineas:
                raise HTTPException(422, "Indica los empleados y valores a pagar")
            saldos = await _saldos_obligaciones(empresa_id, payload.tipo, s)
            valor = 0.0
            for l in payload.lineas:
                if l.valor > saldos.get(l.empleado_id, 0) + 1:
                    raise HTTPException(409, "Un valor supera el saldo provisionado del empleado")
                valor += l.valor
                ledger.append({"empresa_id": empresa_id, "empleado_id": l.empleado_id, "tipo": payload.tipo,
                               "valor": -l.valor, "fecha": payload.fecha, "documento_tipo": OBLIG,
                               "fecha_creacion": ahora()})
            debitos = [Linea(codigo=p[OBLIGACIONES[payload.tipo]], debito=valor)]
            concepto = f"Pago de {payload.tipo}"
        doc = {"empresa_id": empresa_id, "prefijo": "PO", "consecutivo": consecutivo, "numero": numero,
               "tipo": payload.tipo, "fecha": payload.fecha, "valor": valor, "anio": payload.anio, "mes": payload.mes,
               "lineas": [l.model_dump() for l in payload.lineas], "cuenta_tipo": payload.cuenta_tipo,
               "cuenta_id": payload.cuenta_id, "estado": "registrado", "creado_por": usuario["id"],
               "fecha_creacion": ahora()}
        res = await db.nomina_pagos_obligaciones.insert_one(doc, session=s)
        pid = str(res.inserted_id)
        mov = await _movimiento_efectivo(empresa_id, payload.cuenta_tipo, payload.cuenta_id, payload.fecha, valor,
                                         concepto, numero, OBLIG, pid, usuario["id"], s)
        efectivo = _lineas_tesoreria(mov, "")[0]  # solo la línea de caja o banco
        await registrar_asientos(empresa_id, OBLIG, pid, numero, payload.fecha, [*debitos, efectivo], s)
        for e in ledger:
            e["documento_id"] = pid
        if ledger:
            await db.nomina_obligaciones.insert_many(ledger, session=s)
        await auditar(empresa_id, OBLIG, pid, numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.nomina_pagos_obligaciones.find_one({"_id": nuevo}))


@nom.get("/pagos-obligaciones")
async def listar_pagos_obligaciones(
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    cursor = get_db().nomina_pagos_obligaciones.find({"empresa_id": empresa_id}).sort(
        [("fecha", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@nom.post("/pagos-obligaciones/{pid}/anular")
async def anular_pago_obligacion(
    pid: str, payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        pago = await cargar_editable("nomina_pagos_obligaciones", empresa_id, pid, s)
        mov = await db.movimientos_tesoreria.find_one(
            {"empresa_id": empresa_id, "documento_tipo": OBLIG, "documento_id": pid}, session=s)
        if mov and mov.get("conciliado"):
            raise HTTPException(409, "El pago ya está conciliado con el extracto bancario")
        await db.movimientos_tesoreria.delete_many(
            {"empresa_id": empresa_id, "documento_tipo": OBLIG, "documento_id": pid}, session=s)
        await _revertir_documento(empresa_id, OBLIG, pid, s)
        await db.nomina_pagos_obligaciones.update_one(
            {"_id": pago["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, OBLIG, pid, pago["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.nomina_pagos_obligaciones.find_one({"_id": oid(pid)}))


# ---------------------------------------------------------------------------
# Liquidación de contrato
# ---------------------------------------------------------------------------

class LiquidacionFinalEntrada(BaseModel):
    empleado_id: str
    fecha_retiro: str
    causa: Literal["renuncia", "despido_sin_justa_causa", "despido_con_justa_causa",
                   "terminacion_contrato_fijo", "mutuo_acuerdo"]
    dias_salario_pendiente: float = Field(default=0, ge=0)
    dias_vacaciones_disfrutados: float | None = Field(default=None, ge=0)
    promedio_variable: float = Field(default=0, ge=0)
    fecha_fin_contrato: str | None = None
    valores: dict[str, float] = Field(default_factory=dict, description="Ajustes manuales a los valores calculados")


LIQ_FINAL = "nomina_liquidacion_final"
CLAVES_LIQ = ("salario_pendiente", "cesantias", "intereses", "prima", "vacaciones", "indemnizacion")


async def _calcular_final(empresa_id: str, e: LiquidacionFinalEntrada, s=None) -> tuple[dict, dict, dict]:
    db = get_db()
    emp = await db.empleados.find_one({"_id": oid(e.empleado_id, "empleado_id"), "empresa_id": empresa_id}, session=s)
    if not emp:
        raise HTTPException(404, "Empleado no encontrado")
    if emp.get("fecha_retiro"):
        raise HTTPException(409, "El empleado ya fue retirado")
    retiro = _fecha_valida(e.fecha_retiro, "Fecha de retiro")
    if retiro < date.fromisoformat(emp["fecha_ingreso"]):
        raise HTTPException(422, "La fecha de retiro es anterior al ingreso")
    p = await _parametros(empresa_id, retiro.year, s)
    disfrutadas = e.dias_vacaciones_disfrutados
    if disfrutadas is None:
        disfrutadas = 0.0
        async for n in db.nomina_novedades.find(
            {"empresa_id": empresa_id, "empleado_id": e.empleado_id, "tipo": "vacaciones", "activo": {"$ne": False}}, session=s
        ):
            disfrutadas += float(n.get("cantidad") or 0)
    fin_contrato = _fecha_valida(e.fecha_fin_contrato, "Fin del contrato") if e.fecha_fin_contrato else None
    calculo = motor.liquidacion_final(
        {**emp, "id": e.empleado_id}, retiro, e.causa, p, e.dias_salario_pendiente, disfrutadas,
        e.promedio_variable, fecha_fin_contrato=fin_contrato)
    for k, v in e.valores.items():
        if k in CLAVES_LIQ:
            calculo[k] = redondear(v, 0)
    calculo["total"] = float(redondear(sum(calculo[k] for k in CLAVES_LIQ)))
    saldos = {t: (await _saldos_obligaciones(empresa_id, t, s)).get(e.empleado_id, 0.0) for t in OBLIGACIONES}
    return emp, calculo, saldos


@nom.post("/liquidaciones-finales/calcular")
async def calcular_liquidacion_final(
    payload: LiquidacionFinalEntrada,
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    emp, calculo, saldos = await _calcular_final(empresa_id, payload)
    return {"empleado": motor.nombre_empleado(emp), "calculo": calculo, "provisionado": saldos,
            "nota": "No incluye aportes ni retención sobre el salario pendiente; ajústalos en los valores si aplica."}


@nom.post("/liquidaciones-finales", status_code=201)
async def crear_liquidacion_final(
    payload: LiquidacionFinalEntrada,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "crear")),
):
    db = get_db()

    async def _tx(s):
        emp, calculo, saldos = await _calcular_final(empresa_id, payload, s)
        p = await parametros.obtener(empresa_id, s)
        consecutivo = await siguiente_consecutivo(empresa_id, "nomina_liquidacion_final", s)
        numero = formatear_numero("LF", consecutivo)
        doc = {"empresa_id": empresa_id, "prefijo": "LF", "consecutivo": consecutivo, "numero": numero,
               "empleado_id": payload.empleado_id, "empleado_nombre": motor.nombre_empleado(emp),
               "documento": emp.get("numero_documento"), "fecha_retiro": payload.fecha_retiro, "causa": payload.causa,
               "calculo": calculo, "valores": {k: calculo[k] for k in CLAVES_LIQ}, "provisionado": saldos,
               "neto_pagar": calculo["total"], "estado": "liquidada", "pagado": False,
               "creado_por": usuario["id"], "fecha_creacion": ahora()}
        res = await db.nomina_liquidaciones_finales.insert_one(doc, session=s)
        lid = str(res.inserted_id)

        lineas: list[Linea] = []
        ledger = []
        claves = {"cesantias": "nomina_cesantias", "intereses": "nomina_intereses",
                  "prima": "nomina_prima", "vacaciones": "nomina_vacaciones"}
        for tipo, param in claves.items():
            legal, saldo = calculo[tipo], saldos[tipo]
            if saldo:
                lineas.append(Linea(codigo=p[param], debito=saldo, descripcion=f"Cancela provisión de {tipo}"))
                ledger.append({"empresa_id": empresa_id, "empleado_id": payload.empleado_id, "tipo": tipo,
                               "valor": -saldo, "fecha": payload.fecha_retiro, "documento_tipo": LIQ_FINAL,
                               "documento_id": lid, "fecha_creacion": ahora()})
            diferencia = redondear(legal - saldo, 2)
            if diferencia > 0:
                lineas.append(Linea(codigo=_cuenta_emp(emp, "cuenta_gasto_prestaciones", p), debito=diferencia, descripcion=f"{tipo}: mayor valor"))
            elif diferencia < 0:
                lineas.append(Linea(codigo=_cuenta_emp(emp, "cuenta_gasto_prestaciones", p), credito=-diferencia, descripcion=f"{tipo}: reintegro de provisión"))
        lineas.append(Linea(codigo=_cuenta_emp(emp, "cuenta_gasto_salarios", p), debito=calculo["salario_pendiente"]))
        lineas.append(Linea(codigo=p["nomina_gasto_indemnizacion"], debito=calculo["indemnizacion"]))
        lineas.append(Linea(codigo=p["nomina_salarios_por_pagar"], credito=calculo["total"]))
        await registrar_asientos(empresa_id, LIQ_FINAL, lid, numero, payload.fecha_retiro, lineas, s)
        if ledger:
            await db.nomina_obligaciones.insert_many(ledger, session=s)
        await db.empleados.update_one(
            {"_id": emp["_id"]},
            {"$set": {"fecha_retiro": payload.fecha_retiro, "estado": "retirado", "causa_retiro": payload.causa}},
            session=s)
        await auditar(empresa_id, LIQ_FINAL, lid, numero, usuario["id"], "creado", s)
        return res.inserted_id

    nuevo = await en_transaccion(_tx)
    return serializar(await db.nomina_liquidaciones_finales.find_one({"_id": nuevo}))


@nom.get("/liquidaciones-finales")
async def listar_liquidaciones_finales(
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    cursor = get_db().nomina_liquidaciones_finales.find({"empresa_id": empresa_id}).sort(
        [("fecha_retiro", -1), ("consecutivo", -1)])
    return [serializar(d) async for d in cursor]


@nom.post("/liquidaciones-finales/{lid}/anular")
async def anular_liquidacion_final(
    lid: str, payload: Anulacion,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "inactivar")),
):
    db = get_db()

    async def _tx(s):
        doc = await cargar_editable("nomina_liquidaciones_finales", empresa_id, lid, s)
        if doc.get("pagado"):
            raise HTTPException(409, "La liquidación ya fue pagada: anula primero el pago")
        if await db.nomina_electronica.find_one(
            {"empresa_id": empresa_id, "empleado_id": doc["empleado_id"], "estado": {"$ne": "borrador"},
             "mes": int(doc["fecha_retiro"][5:7]), "anio": int(doc["fecha_retiro"][:4])}, session=s
        ):
            raise HTTPException(409, "La nómina electrónica de ese mes ya fue transmitida")
        await _revertir_documento(empresa_id, LIQ_FINAL, lid, s)
        await db.empleados.update_one(
            {"_id": oid(doc["empleado_id"])},
            {"$set": {"estado": "activo"}, "$unset": {"fecha_retiro": "", "causa_retiro": ""}}, session=s)
        await db.nomina_liquidaciones_finales.update_one(
            {"_id": doc["_id"]}, {"$set": marca_anulacion(usuario["id"], payload.motivo)}, session=s)
        await auditar(empresa_id, LIQ_FINAL, lid, doc["numero"], usuario["id"], "anulado", s, {"motivo": payload.motivo})

    await en_transaccion(_tx)
    return serializar(await db.nomina_liquidaciones_finales.find_one({"_id": oid(lid)}))


# ---------------------------------------------------------------------------
# Nómina electrónica: un paquete por empleado y por mes, consolidado
# ---------------------------------------------------------------------------

class MesNomina(BaseModel):
    anio: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)


@nom.post("/electronica/generar")
async def generar_nomina_electronica(
    payload: MesNomina,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "crear")),
):
    """Consolida los pagos del mes (mensuales o quincenales) en un documento por empleado."""
    db = get_db()
    prefijo_mes = f"{payload.anio:04d}-{payload.mes:02d}"
    periodos = [p async for p in db.nomina_periodos.find(
        {"empresa_id": empresa_id, "anio": payload.anio, "mes": payload.mes, **NO_ANULADO})]
    finales = [f async for f in db.nomina_liquidaciones_finales.find(
        {"empresa_id": empresa_id, "fecha_retiro": {"$regex": f"^{prefijo_mes}"}, **NO_ANULADO})]
    if not periodos and not finales:
        raise HTTPException(409, "No hay nómina liquidada en ese mes")
    sin_pagar = [p["numero"] for p in periodos if not p.get("pagado")] + [f["numero"] for f in finales if not f.get("pagado")]
    if sin_pagar:
        raise HTTPException(409, f"Paga primero estas liquidaciones (la DIAN exige la fecha de pago): {', '.join(sin_pagar)}")

    empresa = await db.empresas.find_one({"_id": oid(empresa_id)})
    por_empleado: dict[str, dict] = defaultdict(lambda: {"lineas": [], "fechas": [], "periodos": [], "final": None})
    for p in periodos:
        for l in p["lineas"]:
            d = por_empleado[l["empleado_id"]]
            d["lineas"].append(l)
            d["fechas"].append(p["fecha_pago"])
            d["periodos"].append(p["numero"])
    for f in finales:
        d = por_empleado[f["empleado_id"]]
        d["final"] = {**f["valores"], "fecha_retiro": f["fecha_retiro"]}
        d["fechas"].append(f["fecha_pago"])
        d["periodos"].append(f["numero"])

    resultado = {"generados": [], "omitidos": []}

    async def _tx(s):
        for emp_id, d in por_empleado.items():
            emp = await db.empleados.find_one({"_id": oid(emp_id), "empresa_id": empresa_id}, session=s)
            existente = await db.nomina_electronica.find_one(
                {"empresa_id": empresa_id, "anio": payload.anio, "mes": payload.mes, "empleado_id": emp_id}, session=s)
            if existente and existente["estado"] != "borrador":
                resultado["omitidos"].append({"empleado": existente["empleado_nombre"], "motivo": f"ya está {existente['estado']}"})
                continue
            documento = construir_documento_soporte(empresa, emp, payload.anio, payload.mes, d["lineas"], d["fechas"], d["final"])
            datos = {"empresa_id": empresa_id, "anio": payload.anio, "mes": payload.mes, "empleado_id": emp_id,
                     "empleado_nombre": motor.nombre_empleado(emp), "documento_empleado": emp.get("numero_documento"),
                     "documento": documento, "periodos": sorted(set(d["periodos"])), "estado": "borrador",
                     "devengados": documento["DevengadosTotal"], "deducciones": documento["DeduccionesTotal"],
                     "neto": documento["ComprobanteTotal"], "generado_por": usuario["id"], "fecha_generacion": ahora()}
            if existente:
                await db.nomina_electronica.update_one({"_id": existente["_id"]}, {"$set": datos}, session=s)
            else:
                consecutivo = await siguiente_consecutivo(empresa_id, "nomina_electronica", s)
                datos.update({"prefijo": "NE", "consecutivo": consecutivo, "numero": formatear_numero("NE", consecutivo)})
                await db.nomina_electronica.insert_one(datos, session=s)
            resultado["generados"].append(datos["empleado_nombre"])

    await en_transaccion(_tx)
    return resultado


@nom.get("/electronica")
async def listar_nomina_electronica(
    anio: int | None = None, mes: int | None = None,
    empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    filtro: dict = {"empresa_id": empresa_id}
    if anio:
        filtro["anio"] = anio
    if mes:
        filtro["mes"] = mes
    cursor = get_db().nomina_electronica.find(filtro, {"documento": 0}).sort(
        [("anio", -1), ("mes", -1), ("empleado_nombre", 1)])
    return [serializar(d) async for d in cursor]


@nom.get("/electronica/{nid}/documento")
async def documento_nomina_electronica(
    nid: str, empresa_id: str = Depends(get_empresa_activa), _=Depends(require_permiso("nomina", "leer")),
):
    doc = await get_db().nomina_electronica.find_one({"_id": oid(nid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    return doc["documento"]


@nom.post("/electronica/{nid}/transmitir")
async def transmitir_nomina_electronica(
    nid: str,
    empresa_id: str = Depends(get_empresa_activa),
    usuario: dict = Depends(require_permiso("nomina", "editar")),
):
    db = get_db()
    doc = await db.nomina_electronica.find_one({"_id": oid(nid), "empresa_id": empresa_id})
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    if doc["estado"] in ("enviado", "aceptado"):
        raise HTTPException(409, f"El documento ya está {doc['estado']}")
    try:
        resultado = await get_cliente_nomina().emitir(empresa_id, doc["documento"])
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))
    await db.nomina_electronica.update_one(
        {"_id": doc["_id"]},
        {"$set": {"estado": resultado.get("estado", "enviado"), "cune": resultado.get("cune"),
                  "xml_url": resultado.get("xml_url"), "pdf_url": resultado.get("pdf_url"),
                  "id_externo": resultado.get("id_externo"), "transmitido_por": usuario["id"],
                  "fecha_transmision": ahora()}},
    )
    return {"ok": True, **resultado}


router.include_router(nom)
