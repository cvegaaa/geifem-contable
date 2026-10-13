"""Índices de MongoDB. Se aplican al arrancar la API (operación idempotente)."""
from pymongo.asynchronous.database import AsyncDatabase

# colección -> [(campos, opciones)]
INDICES: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "empresas": [([("nit", 1)], {"unique": True})],
    "usuarios": [
        ([("email", 1)], {"unique": True}),
        ([("empresa_ids", 1)], {}),
    ],
    "terceros": [
        ([("empresa_id", 1), ("numero_documento", 1)], {"unique": True}),
        ([("empresa_id", 1), ("tipo", 1)], {}),
    ],
    "plan_cuentas": [([("empresa_id", 1), ("codigo", 1)], {"unique": True})],
    "tipos_documento": [([("empresa_id", 1), ("prefijo", 1)], {"unique": True})],
    "resoluciones_dian": [([("empresa_id", 1), ("prefijo", 1), ("fecha_fin", -1)], {})],
    "centros_costo": [([("empresa_id", 1), ("codigo", 1)], {"unique": True})],
    "conceptos_retencion": [([("empresa_id", 1), ("tipo", 1), ("nombre", 1)], {"unique": True})],
    "impuestos_config": [([("empresa_id", 1), ("tipo", 1)], {})],
    "unidades_medida": [([("empresa_id", 1), ("abreviatura", 1)], {"unique": True})],
    "formas_pago": [([("empresa_id", 1), ("nombre", 1)], {"unique": True})],
    "productos": [([("empresa_id", 1), ("sku", 1)], {"unique": True})],
    "bodegas": [([("empresa_id", 1), ("nombre", 1)], {"unique": True})],
    "existencias_por_bodega": [
        ([("empresa_id", 1), ("producto_id", 1), ("bodega_id", 1)], {"unique": True}),
        ([("empresa_id", 1), ("bodega_id", 1)], {}),
    ],
    "movimientos_inventario": [
        ([("empresa_id", 1), ("producto_id", 1), ("fecha", 1)], {}),
        ([("empresa_id", 1), ("documento_tipo", 1), ("documento_id", 1)], {}),
    ],
    "facturas": [
        ([("empresa_id", 1), ("fecha", -1)], {}),
        ([("cufe", 1)], {"sparse": True}),
    ],
    "asientos_contables": [
        ([("empresa_id", 1), ("fecha", -1)], {}),
        ([("empresa_id", 1), ("cuenta_puc_id", 1)], {}),
        ([("empresa_id", 1), ("documento_tipo", 1), ("documento_id", 1)], {}),
    ],
    "comprobantes_contables": [
        ([("empresa_id", 1), ("tipo", 1), ("consecutivo", -1)], {}),
        ([("empresa_id", 1), ("fecha", -1)], {}),
    ],
    # Los intentos de inicio de sesión caducan solos a las 2 horas.
    "intentos_login": [
        ([("clave", 1), ("fecha", 1)], {}),
        ([("fecha", 1)], {"expireAfterSeconds": 7200}),
    ],
    "empleados": [([("empresa_id", 1), ("numero_documento", 1)], {"unique": True})],
    "nomina_novedades": [([("empresa_id", 1), ("empleado_id", 1), ("fecha_inicio", 1)], {})],
    "nomina_parametros": [([("empresa_id", 1), ("anio", 1)], {"unique": True})],
    "facturas_recibidas": [
        ([("empresa_id", 1), ("cufe", 1)], {"unique": True}),
        ([("empresa_id", 1), ("fecha", -1)], {}),
    ],
    "anticipos": [([("empresa_id", 1), ("tipo", 1), ("tercero_id", 1)], {})],
    "aplicaciones_anticipo": [([("empresa_id", 1), ("documento_id", 1)], {})],
    "transferencias": [([("empresa_id", 1), ("fecha", -1)], {})],
    "devoluciones_proveedor": [([("empresa_id", 1), ("factura_id", 1)], {})],
    "tarifas_simple": [([("empresa_id", 1)], {"unique": True})],
    "nomina_periodos": [([("empresa_id", 1), ("anio", 1), ("mes", 1), ("tipo", 1)], {})],
    "nomina_obligaciones": [
        ([("empresa_id", 1), ("empleado_id", 1), ("tipo", 1)], {}),
        ([("empresa_id", 1), ("documento_tipo", 1), ("documento_id", 1)], {}),
    ],
    "nomina_electronica": [([("empresa_id", 1), ("anio", 1), ("mes", 1), ("empleado_id", 1)], {"unique": True})],
    "auditoria": [
        ([("empresa_id", 1), ("documento_id", 1), ("fecha_hora", -1)], {}),
        ([("empresa_id", 1), ("fecha_hora", -1)], {}),
    ],
    "contadores": [([("empresa_id", 1), ("clave", 1)], {"unique": True})],
}


async def asegurar_indices(db: AsyncDatabase) -> None:
    for coleccion, indices in INDICES.items():
        for campos, opciones in indices:
            await db[coleccion].create_index(campos, **opciones)
