"""Cliente del proveedor tecnológico DIAN.

El proveedor elegido es Alegra (API REST). La implementación real
(`ClienteAlegra`) se construye en la Fase 2 del ROADMAP; mientras tanto
el sistema usa `ClientePTNoConfigurado`, que responde 501.
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
        raise NotImplementedError("Facturación electrónica no configurada (pendiente integración con Alegra).")

    async def enviar_factura(self, empresa_id, factura):  # pragma: no cover
        raise NotImplementedError("Facturación electrónica no configurada (pendiente integración con Alegra).")

    async def consultar_estado(self, empresa_id, cufe):  # pragma: no cover
        raise NotImplementedError("Facturación electrónica no configurada (pendiente integración con Alegra).")


def get_cliente_pt() -> ClientePT:
    """Factory: devolverá el cliente Alegra configurado por empresa (Fase 2)."""
    return ClientePTNoConfigurado()
