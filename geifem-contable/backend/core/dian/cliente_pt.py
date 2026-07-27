"""Cliente del Proveedor Tecnológico (Factus / Alanube).

FASE 1: solo el contrato de la interfaz. Las llamadas reales (OAuth2 + REST)
se implementan en fases posteriores cuando se disponga de credenciales.
"""
from abc import ABC, abstractmethod
from typing import Any


class ClientePT(ABC):
    """Interfaz común de todos los proveedores tecnológicos DIAN."""

    @abstractmethod
    async def autenticar(self, credenciales: dict[str, Any]) -> str:
        """Devuelve un access token."""

    @abstractmethod
    async def enviar_factura(self, empresa_id: str, factura: dict[str, Any]) -> dict[str, Any]:
        """Envía una factura y devuelve {cufe, xml_url, pdf_url, estado}."""

    @abstractmethod
    async def consultar_estado(self, empresa_id: str, cufe: str) -> dict[str, Any]:
        """Consulta el estado DIAN de una factura ya enviada."""


class ClientePTNoConfigurado(ClientePT):
    """Implementación por defecto — lanza error si se invoca sin PT real."""

    async def autenticar(self, credenciales):  # pragma: no cover
        raise NotImplementedError("Proveedor Tecnológico DIAN no configurado (Fase 1).")

    async def enviar_factura(self, empresa_id, factura):  # pragma: no cover
        raise NotImplementedError("Proveedor Tecnológico DIAN no configurado (Fase 1).")

    async def consultar_estado(self, empresa_id, cufe):  # pragma: no cover
        raise NotImplementedError("Proveedor Tecnológico DIAN no configurado (Fase 1).")


def get_cliente_pt() -> ClientePT:
    """Factory: devolverá el PT configurado por empresa en fases posteriores."""
    return ClientePTNoConfigurado()
