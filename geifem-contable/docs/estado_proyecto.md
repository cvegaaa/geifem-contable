# GEIFEM Contable — Informe de estado del proyecto

_Actualizado: 26 de agosto de 2026_

## 1. Acceso de revisión (preview)

El backend FastAPI **no corre dentro del preview**, por eso existe un usuario
demo local en el frontend para revisar la interfaz:

- **Usuario:** `demo@geifem.co`
- **Contraseña:** `demo1234`

Este acceso vive en `frontend/src/shared/auth/AuthContext.jsx` y **debe
eliminarse antes de producción**. Con el backend corriendo (`uvicorn main:app
--port 8000`) el login usa credenciales reales contra `/api/auth/login`.

## 2. Estado general

| Capa | Estado |
|---|---|
| Frontend React + Vite + Tailwind | Andamiaje completo, compila sin errores |
| Backend FastAPI + Motor | Rutas de las 3 fases implementadas |
| MongoDB (índices + esquema) | `database/init_indexes.py` y `database/README.md` |
| Multi-tenant (`X-Empresa-Id`) | Funcional en frontend y backend |
| Auth JWT + 3 roles + permisos | Funcional |
| Facturación electrónica DIAN | Solo contrato/interfaz, sin credenciales de PT |

## 3. Lo que ya está construido

### Configuración
Datos de empresa, terceros, plan de cuentas (semillas PUC SIMPLE/Común),
resoluciones DIAN, tipos de documento, impuestos, formas de pago, unidades de
medida, centros de costo, usuarios y roles con permisos por módulo/acción.

### Contabilidad
Comprobantes de apertura, ajuste y cierre; notas contables; consulta de
comprobantes con detalle; auditoría de comprobantes. Validación de partida
doble.

### Facturación
Factura de venta multi-ítem con numeración DIAN por resolución y
contabilización espejo (1305 / 4135 / 2408); notas crédito y débito
(reversión); documento equivalente POS.

### Inventario
Catálogo de productos, bodegas, kardex por **promedio ponderado**, stub de
sincronización POS/online.

### Compras (Fase 2)
Órdenes de compra, recepción de mercancía (entrada a inventario con recálculo
de costo promedio), facturas de proveedor con retenciones y contabilización
(1435/6205, 2365).

### Tesorería (Fase 2 y 3)
Caja, bancos, CxC/CxP con cruce de cartera, flujo de caja y **conciliación
bancaria automática** (carga de extracto, emparejamiento por valor/signo/fecha
con tolerancia, confirmación manual).

### Retenciones (Fase 2)
Motor de ReteFuente, ReteICA y ReteIVA con bases mínimas en UVT (52.374 COP
para 2026) y conceptos parametrizables, conectado a facturas de proveedor y al
Formulario 350.

### Reportes
Catálogo de 7 categorías espejado entre backend y frontend, con ~26
generadores: ventas, administrativos, financieros, contables (balance de
prueba, libro diario, libro mayor, auxiliar por tercero), fiscales
(Formulario 300 IVA, 260 SIMPLE, 350 retenciones), libros oficiales con
folio, exportables y **calendario tributario 2026** (vencimientos por dígito
de NIT y régimen, con ajuste por días hábiles y festivos).

### Información exógena (Fase 3)
Formatos 1001, 1003, 1005, 1006, 1007, 1008 y 1009.

### Jobs
`jobs/alertas_vencimientos.py`: alertas de cartera vencida y de obligaciones
tributarias próximas.

## 4. Lo que falta por construir

### Bloqueantes para producción
1. **Integración real con el Proveedor Tecnológico DIAN** (Factus / Alanube):
   hoy solo existe la interfaz `core/dian/cliente_pt.py`. Falta implementar
   `autenticar`, `enviar_factura`, `consultar_estado`, el cifrado de
   `pt_config` por empresa y el procesamiento real de webhooks (CUFE, XML,
   PDF, estado DIAN).
2. **Eliminar el usuario demo** del frontend y cerrar `/api/auth/registro`
   para que solo un admin autenticado pueda crear usuarios.
3. **Persistencia real verificada contra MongoDB Atlas**: correr
   `init_indexes.py` y probar los flujos completos contra la base productiva.
4. **Cifrado de credenciales** (`pt_config`, claves de bancos) y rotación de
   `JWT_SECRET`.

### Funcionalidad pendiente
5. **Formato 2276** (rentas de trabajo): requiere un módulo de **nómina** que
   no está en la estructura autorizada. Pendiente de tu aprobación.
6. **Informe de mandatos** (ingresos para terceros): marcado como Fase 3, sin
   generador.
7. **Ventas por vendedor**: requiere asociar vendedor a la factura; hoy está
   marcado como Fase 2 sin implementar.
8. **Sincronización POS / tienda online**: hoy es un stub; falta definir con
   qué plataformas se integra.
9. **Importación de extractos bancarios en formato de archivo** (hoy solo
   pegado de texto): faltan parsers por banco (CSV/OFX de Bancolombia, Davivienda, etc.).
10. **Exportación real a Excel/PDF**: los reportes marcados "Excel"/"PDF"
    devuelven datos JSON; falta la generación de archivos.

### Calidad y operación
11. **Pruebas automatizadas**: no hay suite de tests en backend ni frontend.
12. **Validaciones de negocio adicionales**: cierre de periodos contables,
    bloqueo de edición sobre documentos ya transmitidos a la DIAN,
    consecutivos sin huecos.
13. **Paginación y filtros del lado del servidor** en listados grandes.
14. **Auditoría/trazabilidad** completa de cambios por usuario.
15. **Logo oficial**: pendiente subir el archivo definitivo para reemplazar el
    placeholder en `shared/layout/Logo/`.
16. **CI/CD y despliegue**: intencionalmente fuera de alcance de este
    repositorio (Vercel + Railway + Atlas, manual).

## 5. Recomendación de siguiente iteración

1. Conectar la base MongoDB Atlas real y validar los flujos de punta a punta.
2. Contratar/configurar el Proveedor Tecnológico e implementar `ClientePT`.
3. Endurecer autenticación (quitar demo, cerrar registro, cifrar secretos).
4. Definir con vos si se autoriza el módulo de nómina para el Formato 2276.
