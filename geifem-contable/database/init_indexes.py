"""Inicializa índices MongoDB para GEIFEM Contable.

Uso:
    python init_indexes.py

Lee MONGO_URI y DB_NAME desde variables de entorno (o desde el .env del backend).
"""
import asyncio
import os
import sys
from pathlib import Path

# Permitir importar la configuración del backend si se ejecuta desde ../database
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "geifem_contable")

# (colección, [(spec, kwargs)])
INDICES = {
    "empresas": [([("nit", 1)], {"unique": True})],
    "usuarios": [([("email", 1)], {"unique": True})],
    "terceros": [
        ([("empresa_id", 1)], {}),
        ([("empresa_id", 1), ("numero_documento", 1)], {"unique": True}),
        ([("empresa_id", 1), ("tipo", 1)], {}),
    ],
    "plan_cuentas": [
        ([("empresa_id", 1)], {}),
        ([("empresa_id", 1), ("codigo", 1)], {"unique": True}),
    ],
    "tipos_documento": [([("empresa_id", 1), ("prefijo", 1)], {"unique": True})],
    "resoluciones_dian": [
        ([("empresa_id", 1)], {}),
        ([("empresa_id", 1), ("prefijo", 1), ("fecha_fin", -1)], {}),
    ],
    "centros_costo": [([("empresa_id", 1), ("codigo", 1)], {"unique": True})],
    "impuestos_config": [([("empresa_id", 1), ("tipo", 1)], {})],
    "unidades_medida": [([("empresa_id", 1), ("abreviatura", 1)], {"unique": True})],
    "formas_pago": [([("empresa_id", 1), ("nombre", 1)], {"unique": True})],
    "productos": [
        ([("empresa_id", 1)], {}),
        ([("empresa_id", 1), ("sku", 1)], {"unique": True}),
    ],
    "movimientos_inventario": [
        ([("empresa_id", 1), ("producto_id", 1), ("fecha", -1)], {}),
    ],
    "facturas": [
        ([("empresa_id", 1), ("fecha", -1)], {}),
        ([("cufe", 1)], {"sparse": True}),
    ],
    "asientos_contables": [
        ([("empresa_id", 1), ("fecha", -1)], {}),
        ([("empresa_id", 1), ("cuenta_puc_id", 1)], {}),
    ],
    "comprobantes_contables": [
        ([("empresa_id", 1), ("tipo", 1), ("consecutivo", -1)], {}),
        ([("empresa_id", 1), ("fecha", -1)], {}),
    ],
    "auditoria_comprobantes": [
        ([("comprobante_id", 1), ("fecha_hora", -1)], {}),
    ],
}


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    for coleccion, indices in INDICES.items():
        for spec, kwargs in indices:
            nombre = await db[coleccion].create_index(spec, **kwargs)
            print(f"  ✓ {coleccion}: {nombre}")
    print("Índices creados.")


if __name__ == "__main__":
    asyncio.run(main())
