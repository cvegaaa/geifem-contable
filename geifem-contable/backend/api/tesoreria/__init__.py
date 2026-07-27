"""Tesorería — FASE 2 placeholder (F3 para conciliación auto). Router cableado."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/tesoreria", tags=["tesoreria"])

_F2 = "Módulo pendiente — Fase 2"
_F3 = "Módulo pendiente — Fase 3"


@router.get("/health")
async def health():
    raise HTTPException(501, _F2)


@router.get("/caja")
async def caja():
    raise HTTPException(501, _F2)


@router.get("/bancos")
async def bancos():
    raise HTTPException(501, _F2)


@router.get("/cxc-cxp")
async def cxc_cxp():
    raise HTTPException(501, _F2)


@router.get("/flujo-caja")
async def flujo_caja():
    raise HTTPException(501, _F2)


@router.get("/conciliacion-bancaria-auto")
async def conciliacion_auto():
    raise HTTPException(501, _F3)
