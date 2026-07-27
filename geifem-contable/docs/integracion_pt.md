# Integración con Proveedor Tecnológico (PT)

Fase 1 deja únicamente el **contrato** (interfaz) para que la lógica de
facturación electrónica se conecte a un PT (Factus, Alanube u otros) sin
tocar el resto del sistema.

## Archivos relevantes
- `backend/core/dian/cliente_pt.py` — clase abstracta `ClientePT` y factory
  `get_cliente_pt()`.
- `backend/core/dian/numeracion.py` — resolución del siguiente consecutivo
  DIAN por empresa/tipo de documento.
- `backend/core/dian/webhooks.py` — recepción de callbacks del PT.

## Método esperado por implementación real
```python
class MiPT(ClientePT):
    async def autenticar(self, credenciales: dict) -> str: ...
    async def enviar_factura(self, empresa_id: str, factura: dict) -> dict: ...
    async def consultar_estado(self, empresa_id: str, cufe: str) -> dict: ...
```

`enviar_factura` debe devolver como mínimo:
```json
{ "cufe": "...", "xml_url": "...", "pdf_url": "...", "estado_dian": "aceptado" }
```

## Configuración por empresa
La configuración PT (endpoint, client_id, client_secret) se guarda cifrada
en el campo `pt_config` del documento `empresas`. **Las credenciales reales
NO se almacenan en el repositorio ni en variables globales.** Se inyectan
por empresa cuando se instancia el PT.
