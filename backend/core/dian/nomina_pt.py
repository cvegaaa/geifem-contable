"""Nómina electrónica: documento soporte de pago de nómina electrónica (DIAN).

La obligación nació en la Resolución 000013 de 2021 y hoy está compilada en la
Resolución 000227 de 2025. Se genera **por empleado y por mes** (consolidando todos los
pagos del mes, sin importar si se pagó mensual o quincenal) y se transmite dentro del
plazo del mes siguiente, a través de un proveedor tecnológico (Alegra).

Este módulo hace dos cosas:
1. `construir_documento_soporte`: arma el paquete mensual consolidado de un empleado con la
   estructura del anexo técnico (devengados, deducciones, pagos, periodo, trabajador, empleador).
   Los nombres de campos siguen el anexo; el proveedor tecnológico los mapea a su API.
2. `ClienteNominaPT`: interfaz del proveedor. La implementación real contra Alegra queda
   pendiente de confirmar su API de emisión de nómina electrónica y de las credenciales de
   cada empresa; mientras tanto el sistema responde 501 al transmitir y deja el paquete listo
   (se puede descargar en JSON).
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from core.nomina import dias_comerciales, nombre_empleado
from core.dinero import redondear

TIPO_DOCUMENTO_DIAN = {"CC": "13", "NIT": "31", "CE": "22", "PA": "41", "TI": "12", "RC": "11", "TE": "21", "PEP": "47"}
TIPO_CONTRATO_DIAN = {"indefinido": "2", "fijo": "1", "obra_labor": "3", "aprendizaje": "4", "practicas": "5"}
FORMA_PAGO_DIAN = {"mensual": "1", "quincenal": "2"}


def _suma(lineas: list[dict], f) -> float:
    return float(redondear(sum(f(l) for l in lineas)))


def construir_documento_soporte(
    empresa: dict, empleado: dict, anio: int, mes: int, lineas: list[dict], fechas_pago: list[str],
    liquidacion_final: dict | None = None, medio_pago: dict | None = None,
) -> dict[str, Any]:
    """Paquete mensual consolidado de un empleado.

    `lineas`: las liquidaciones del empleado en los periodos del mes (mensual o quincenas).
    """
    ingreso = empleado["fecha_ingreso"]
    retiro = (liquidacion_final or {}).get("fecha_retiro") or empleado.get("fecha_retiro")
    inicio = f"{anio:04d}-{mes:02d}-01"
    fin_mes = date(anio + (mes == 12), mes % 12 + 1, 1)
    fin = (retiro if retiro and retiro < fin_mes.isoformat() else f"{anio:04d}-{mes:02d}-{(fin_mes - date.resolution).day:02d}")
    lf = liquidacion_final or {}

    def dev(clave):
        return _suma(lineas, lambda l: l["devengos"][clave])

    horas_por_tipo = {}
    for l in lineas:
        for t, v in l["devengos"]["horas"].items():
            horas_por_tipo[t] = horas_por_tipo.get(t, 0) + v

    dias_trabajados = _suma(lineas, lambda l: l["dias_trabajados"])
    devengados = {
        "Basico": {"DiasTrabajados": dias_trabajados, "SueldoTrabajado": dev("sueldo")},
        "Transporte": {"AuxilioTransporte": dev("aux_transporte")},
        "HorasExtrasYRecargos": {t: v for t, v in horas_por_tipo.items()},
        "Vacaciones": {"Pago": dev("vacaciones") + lf.get("vacaciones", 0)},
        "Primas": {"Pago": lf.get("prima", 0)},
        "Cesantias": {"Pago": lf.get("cesantias", 0), "PagoIntereses": lf.get("intereses", 0)},
        "Incapacidades": {"Pago": dev("incapacidad_empleador") + dev("incapacidad_a_cargo_eps_arl")},
        "Licencias": {"LicenciaRemunerada": dev("licencia_remunerada")},
        "Comisiones": dev("comisiones"),
        "BonificacionSalarial": dev("bonificacion_salarial"),
        "BonificacionNoSalarial": dev("no_salariales"),
        "Indemnizacion": lf.get("indemnizacion", 0),
        "OtrosConceptos": lf.get("salario_pendiente", 0),
    }
    devengados_total = float(redondear(
        _suma(lineas, lambda l: l["total_devengado"])
        + lf.get("prima", 0) + lf.get("cesantias", 0) + lf.get("intereses", 0)
        + lf.get("indemnizacion", 0) + lf.get("salario_pendiente", 0)
        + (lf.get("vacaciones", 0))
    ))

    salud = _suma(lineas, lambda l: l["deducciones"]["salud"])
    pension = _suma(lineas, lambda l: l["deducciones"]["pension"])
    ibc = _suma(lineas, lambda l: l["ibc"])
    deducciones = {
        "Salud": {"Porcentaje": 4.0, "Deduccion": salud},
        "FondoPension": {"Porcentaje": 4.0, "Deduccion": pension},
        "FondoSolidaridadPensional": {"Deduccion": _suma(lineas, lambda l: l["deducciones"]["fsp"])},
        "RetencionFuente": _suma(lineas, lambda l: l["deducciones"]["retefuente"]),
        "Libranzas": [
            {"Descripcion": o["tipo"], "Deduccion": o["valor"]}
            for l in lineas for o in l["deducciones"]["otras"]
        ],
    }
    deducciones_total = _suma(lineas, lambda l: l["total_deducciones"])

    pago = {"Forma": FORMA_PAGO_DIAN.get(empleado.get("frecuencia_pago", "mensual"), "1"),
            "Metodo": (medio_pago or {}).get("metodo", "42"),  # 42 = consignación bancaria
            "Banco": empleado.get("banco"), "TipoCuenta": empleado.get("tipo_cuenta"),
            "NumeroCuenta": empleado.get("numero_cuenta")}

    return {
        "InformacionGeneral": {"TipoXML": "102", "Periodo": f"{anio:04d}-{mes:02d}", "Moneda": "COP"},
        "Empleador": {
            "RazonSocial": empresa.get("razon_social"), "NIT": empresa.get("nit"), "DV": empresa.get("dv"),
            "Pais": "CO", "Municipio": empresa.get("ciudad"), "Direccion": empresa.get("direccion"),
        },
        "Trabajador": {
            "TipoTrabajador": empleado.get("tipo_trabajador", "01"),
            "SubTipoTrabajador": empleado.get("subtipo_trabajador", "00"),
            "TipoDocumento": TIPO_DOCUMENTO_DIAN.get(empleado.get("tipo_documento", "CC"), "13"),
            "NumeroDocumento": empleado.get("numero_documento"),
            "PrimerApellido": empleado.get("primer_apellido"), "SegundoApellido": empleado.get("segundo_apellido"),
            "PrimerNombre": empleado.get("primer_nombre"), "OtrosNombres": empleado.get("otros_nombres"),
            "SalarioIntegral": bool(empleado.get("salario_integral")),
            "TipoContrato": TIPO_CONTRATO_DIAN.get(empleado.get("tipo_contrato", "indefinido"), "2"),
            "Sueldo": float(empleado["salario_basico"]), "CodigoTrabajador": empleado.get("numero_documento"),
        },
        "Periodo": {
            "FechaIngreso": ingreso, "FechaRetiro": retiro,
            "FechaLiquidacionInicio": inicio, "FechaLiquidacionFin": fin,
            "TiempoLaborado": dias_comerciales(date.fromisoformat(max(ingreso, inicio)), date.fromisoformat(fin)),
        },
        "Pago": pago,
        "FechasPagos": sorted(set(fechas_pago)),
        "Devengados": devengados,
        "Deducciones": deducciones,
        "IBC": ibc,
        "DevengadosTotal": devengados_total,
        "DeduccionesTotal": deducciones_total,
        "ComprobanteTotal": redondear(devengados_total - deducciones_total, 0),
        "Nombre": nombre_empleado(empleado),
    }


class ClienteNominaPT(ABC):
    """Proveedor tecnológico de nómina electrónica (Alegra)."""

    @abstractmethod
    async def emitir(self, empresa_id: str, documento: dict[str, Any]) -> dict[str, Any]:
        """Transmite el documento a la DIAN y devuelve {cune, estado, xml_url, pdf_url, id_externo}."""

    @abstractmethod
    async def consultar(self, empresa_id: str, id_externo: str) -> dict[str, Any]:
        """Consulta el estado del documento en la DIAN."""


class ClienteNominaNoConfigurado(ClienteNominaPT):
    MENSAJE = (
        "La transmisión de nómina electrónica con Alegra aún no está configurada: falta confirmar su API de "
        "emisión y registrar las credenciales de la empresa. El paquete mensual ya queda generado y se puede "
        "descargar."
    )

    async def emitir(self, empresa_id, documento):  # pragma: no cover
        raise NotImplementedError(self.MENSAJE)

    async def consultar(self, empresa_id, id_externo):  # pragma: no cover
        raise NotImplementedError(self.MENSAJE)


def get_cliente_nomina() -> ClienteNominaPT:
    """Factory: devolverá el cliente de Alegra configurado por empresa."""
    return ClienteNominaNoConfigurado()
