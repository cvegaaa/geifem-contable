"""Integración DIAN — Fase 1: solo contrato/interfaz. Sin credenciales reales."""
from .cliente_pt import ClientePT
from .numeracion import obtener_siguiente_consecutivo
from .webhooks import router as webhooks_router

__all__ = ["ClientePT", "obtener_siguiente_consecutivo", "webhooks_router"]
