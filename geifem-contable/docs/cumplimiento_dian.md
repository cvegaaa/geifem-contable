# Cumplimiento DIAN — GEIFEM Contable

## Alcance Fase 1
- Configuración de rangos de numeración (resoluciones DIAN) por empresa y por
  tipo de documento.
- Generación local de comprobantes contables (ajuste, notas, apertura, cierre).
- Registro de facturas de venta como borrador. **La firma electrónica y el
  envío real a la DIAN se hacen a través del Proveedor Tecnológico (PT)**;
  Fase 1 deja el contrato listo (`backend/core/dian/cliente_pt.py`).

## Régimenes soportados
- **SIMPLE**: sin IVA operativo; formulario 260 anual/bimestral según
  actividad.
- **Común**: IVA 19% (u otras tarifas configurables); formulario 300.

## Formularios previstos
| Fase | Formulario                    | Endpoint                                    |
|------|-------------------------------|---------------------------------------------|
| 1    | Form 300 IVA                  | `GET /api/reportes/form-300-iva`            |
| 1    | Form 260 SIMPLE               | `GET /api/reportes/form-260-simple`         |
| 1    | Estados financieros           | `GET /api/reportes/estados-financieros`     |
| 2    | Form 350 Retenciones          | `GET /api/reportes/form-350-retenciones`    |
| 2    | Libros oficiales              | `GET /api/reportes/libros-oficiales`        |
| 3    | Información exógena           | `GET /api/reportes/exogena`                 |

## CUFE
Devuelto por el PT en la respuesta de `enviar_factura`. Se persiste en la
colección `facturas` y se indexa como campo único (sparse).

## Webhooks
El PT notifica cambios de estado (`acuse` / `aceptado` / `rechazado`) en
`POST /api/dian/webhooks/estado`. La verificación de firma se implementa al
configurar el PT.
