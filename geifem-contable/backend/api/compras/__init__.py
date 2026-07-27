"""Compras — FASE 2 placeholder. Router cableado, endpoints devuelven 501."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/compras", tags=["compras"])

_PENDIENTE = "Módulo pendiente — Fase 2"


@router.get("/health")
async def health():
    raise HTTPException(501, _PENDIENTE)


@router.get("/ordenes-compra")
async def ordenes_compra():
    raise HTTPException(501, _PENDIENTE)


@router.get("/recepcion-mercancia")
async def recepcion_mercancia():
    raise HTTPException(501, _PENDIENTE)


@router.get("/facturas-proveedor")
async def facturas_proveedor():
    raise HTTPException(501, _PENDIENTE)


@router.get("/retenciones")
async def retenciones():
    raise HTTPException(501, _PENDIENTE)
