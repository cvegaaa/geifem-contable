"""Job de alertas de cartera básica — FASE 1.

Recorre CxC vencidas y genera alertas. En Fase 1 solo un stub que puede
invocarse manualmente o desde un scheduler externo (cron de Railway).
"""
import asyncio
from datetime import date, timedelta

from db import get_db


async def revisar_cartera_vencida(dias_umbral: int = 0) -> list[dict]:
    """Devuelve lista de CxC vencidas hasta hoy - dias_umbral."""
    db = get_db()
    corte = (date.today() - timedelta(days=dias_umbral)).isoformat()
    cursor = db.cxc.find({"fecha_vencimiento": {"$lt": corte}, "saldo": {"$gt": 0}})
    return [doc async for doc in cursor]


if __name__ == "__main__":  # pragma: no cover
    resultados = asyncio.run(revisar_cartera_vencida())
    print(f"CxC vencidas: {len(resultados)}")
