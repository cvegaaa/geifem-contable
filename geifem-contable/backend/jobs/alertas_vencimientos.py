"""Job de alertas — cartera vencida (Fase 1) + calendario tributario (Fase 3).

Recorre CxC vencidas y las obligaciones fiscales próximas a vencer de cada
empresa. Puede invocarse manualmente o desde un scheduler externo (cron).
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


async def alertas_calendario_tributario(dias: int = 15) -> list[dict]:
    """Obligaciones fiscales que vencen en los próximos `dias` días, por empresa."""
    from core.calendario import calendario_empresa

    db = get_db()
    hoy = date.today()
    alertas: list[dict] = []
    async for emp in db.empresas.find({}, {"nit": 1, "razon_social": 1, "regimen_tributario": 1}):
        obligaciones = calendario_empresa(
            str(emp.get("nit", "") or ""), emp.get("regimen_tributario", "COMUN"), hoy.year, hoy
        )
        for ob in obligaciones:
            for f in ob["fechas"]:
                if f["estado"] == "proxima" and f.get("dias") is not None and f["dias"] <= dias:
                    alertas.append({
                        "empresa_id": str(emp["_id"]),
                        "razon_social": emp.get("razon_social", ""),
                        "obligacion": ob["obligacion"],
                        "periodo": f["periodo"],
                        "fecha_limite": f["fecha_limite"],
                        "dias_restantes": f["dias"],
                    })
    alertas.sort(key=lambda a: a["fecha_limite"])
    return alertas


if __name__ == "__main__":  # pragma: no cover
    vencidas = asyncio.run(revisar_cartera_vencida())
    print(f"CxC vencidas: {len(vencidas)}")
    fiscales = asyncio.run(alertas_calendario_tributario())
    for a in fiscales:
        print(f"[{a['fecha_limite']}] {a['razon_social']}: {a['obligacion']} ({a['periodo']})")
