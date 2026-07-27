"""Reportes — FASE 1 parcial (base) + placeholders Fase 2/3.

Todos los reportes reciben rango (desde, hasta) desde el componente compartido
`selector-rango-fechas` del frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


async def _rango_facturas(empresa_id: str, desde: str, hasta: str):
    db = get_db()
    cursor = db.facturas.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}}
    )
    return [d async for d in cursor]


# ---------- FASE 1 ----------
@router.get("/form-300-iva")
async def form_300_iva(
    desde: str = Query(...),
    hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    facturas = await _rango_facturas(empresa_id, desde, hasta)
    base = sum(f.get("subtotal", 0) for f in facturas)
    iva = sum(f.get("iva", 0) for f in facturas)
    return {"periodo": {"desde": desde, "hasta": hasta}, "base_gravable": base, "iva_generado": iva, "facturas": len(facturas)}


@router.get("/form-260-simple")
async def form_260_simple(
    desde: str = Query(...),
    hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    facturas = await _rango_facturas(empresa_id, desde, hasta)
    ingresos = sum(f.get("total", 0) for f in facturas)
    return {"periodo": {"desde": desde, "hasta": hasta}, "ingresos_brutos": ingresos, "facturas": len(facturas)}


@router.get("/estados-financieros")
async def estados_financieros(
    desde: str = Query(...),
    hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    """Balance y P&G mínimos derivados de asientos_contables."""
    db = get_db()
    pipeline = [
        {"$match": {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}}},
        {"$group": {"_id": "$cuenta_puc_id", "debitos": {"$sum": "$debito"}, "creditos": {"$sum": "$credito"}}},
    ]
    saldos = [d async for d in db.asientos_contables.aggregate(pipeline)]
    return {"periodo": {"desde": desde, "hasta": hasta}, "saldos_por_cuenta": saldos}


# ---------- FASE 2 / 3 (stubs 501) ----------
@router.get("/form-350-retenciones")
async def form_350(_=Depends(require_permiso("reportes", "leer"))):
    raise HTTPException(501, "Form-350 Retenciones — pendiente Fase 2")


@router.get("/libros-oficiales")
async def libros_oficiales(_=Depends(require_permiso("reportes", "leer"))):
    raise HTTPException(501, "Libros oficiales — pendiente Fase 2")


@router.get("/exogena")
async def exogena(_=Depends(require_permiso("reportes", "leer"))):
    raise HTTPException(501, "Exógena multi-bodega — pendiente Fase 3")
