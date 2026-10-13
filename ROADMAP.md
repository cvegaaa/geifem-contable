# Ruta de trabajo — GEIFEM Contable

Documento vivo: se actualiza con cada avance. Marca `[x]` lo terminado **y
verificado**, deja `[ ]` lo pendiente y anota en la bitácora qué cambió.

## Principio rector

**Nada se mueve sin dejar un registro contable.** Toda transacción de cualquier módulo genera su asiento en el libro, en la misma transacción de base de datos, atado a una cuenta contable parametrizable (empresa, producto, concepto de retención, impuesto, caja, banco, nómina). Excepciones deliberadas, que no son transacciones contables: órdenes de compra, comprobantes en borrador, conciliación bancaria (marca, no mueve) y el recálculo del kardex (efecto de documentos que ya tienen su asiento). Anular un documento revierte su asiento y conserva su número y su rastro en la auditoría.

## Decisiones vigentes

| Tema | Decisión | Fecha |
|---|---|---|
| Base de datos | MongoDB 8 en replica set (transacciones) | 2026-10-12 |
| Dinero | Valores en `float` con redondeo exacto al centavo (`core/dinero.py`, ROUND_HALF_UP) en cada punto de cálculo y cuadre en centavos; no se migra a `Decimal128` | 2026-10-13 |
| Orden de trabajo | Funcionalidad general → detalle módulo por módulo → integración con Alegra → integración de agentes (MCP) | 2026-10-13 |
| Facturación electrónica | Vía **Alegra** (API) como proveedor tecnológico; GEIFEM es el libro contable oficial | 2026-10-12 |
| Despliegue | VPS propio con **Easypanel**; servicios Docker (mongo, backend, frontend/nginx) | 2026-10-12 |
| Sesión | JWT en cookie `httpOnly`; frontend y API en el mismo origen (proxy nginx/Vite) | 2026-10-12 |
| Régimen | `regimen_tributario` (ORDINARIO/SIMPLE) separado de `responsable_iva` | 2026-10-12 |

## Fase 0 — Que corra y sea seguro · 🟢 cerrada (queda el primer despliegue)

- [x] Limpieza: plantilla inicial (`_legacy-scaffold`), usuario demo, stubs (sync POS, webhook sin autenticación, numeración sin uso), `.pyc` versionados, documentos desactualizados; estructura de carpetas aplanada.
- [x] Dependencias actualizadas y mínimas. Backend: FastAPI, PyMongo async (reemplaza Motor), PyJWT (reemplaza python-jose), bcrypt (reemplaza passlib), email-validator. Frontend: React 18, React Router 7, Vite 8, Tailwind 4, axios. `npm audit`: 0 vulnerabilidades.
- [x] Registro público = cuenta + empresa en una transacción, con PUC semilla (incluye todas las cuentas que usan los asientos automáticos) y bodega principal.
- [x] Sesión en cookie `httpOnly`, endpoint de logout; el frontend ya no guarda el token.
- [x] Aislamiento multiempresa: sin bypass de admin; listado de usuarios y auditoría filtrados por empresa; el cliente no puede fijar `empresa_id`.
- [x] Gestión de usuarios solo para admin, sin poder asignar empresas ajenas.
- [x] Pantallas de registro, datos de empresa (editar la activa / crear otra) y selector de empresa que recarga la vista.
- [x] Infraestructura Docker lista para Easypanel: imagen de Mongo con replica set + autenticación, backend, frontend con nginx (proxy `/api`, cabeceras de seguridad), `docker-compose.yml`.
- [x] Pruebas automatizadas de autenticación y aislamiento (`backend/tests/`).
- [x] Pruebas ejecutadas contra Mongo en replica set: 11/11 pasan.
- [x] Stack completo con `docker compose up --build` (modo producción): salud OK, documentación de la API oculta, cabeceras de seguridad; registro, login/logout y pantallas de empresa, PUC y bodegas verificados en el navegador.
- [x] Límite de intentos de login y de registros por IP (contadores en Mongo con TTL).
- [ ] Primer despliegue en el VPS con Easypanel y dominio con HTTPS (procedimiento del propietario: guía en `docs/operacion.md`).
- [x] Respaldo automático diario de Mongo (`mongodump`) con retención y subida opcional fuera del VPS (rclone); restauración verificada.
- [x] CI (GitHub Actions) con pruebas del backend contra Mongo en replica set y compilación del frontend.
- [x] Cabeceras de seguridad en nginx (CSP, HSTS) y cambio de contraseña que invalida las demás sesiones.

## Fase 1 — Núcleo contable confiable · 🟡 en curso

**Hecho (adelantado por la revisión de usabilidad del 2026-10-12):**

- [x] **Motor común de documentos** (`backend/core/documentos.py`): numeración automática y atómica por tipo (colección `contadores`), transacción por documento, auditoría de cada cambio.
- [x] **Editar, duplicar y anular** en todos los documentos: comprobantes (CA, NT, AP, CC), facturas (resolución DIAN), POS, notas (NC/ND), órdenes de compra (OC), entradas de mercancía (EM), facturas de proveedor (FP), movimientos de caja/banco (MT), recibos y egresos (RC/CE) y ajustes de inventario (AI). Editar revierte y vuelve a aplicar los efectos; anular conserva el número y revierte los efectos (no hay borrado físico: la secuencia no tiene huecos).
- [x] **Un solo libro**: los comprobantes contabilizados ya llegan a reportes (antes no aparecían); todos los asientos quedan ligados a su documento.
- [x] Asientos validados: se rechazan si falta una cuenta, si la cuenta es de agrupación o si no cuadran (antes se omitían líneas en silencio).
- [x] Kardex recalculado desde los movimientos: editar o anular una compra antigua deja existencias y costo promedio coherentes; se impide dejar existencias negativas.
- [x] La venta (factura y POS) descuenta inventario y registra costo de venta (6135 / 1435); productos marcados como servicio no mueven inventario.
- [x] Notas crédito/débito ajustan el saldo de la factura y no pueden superarlo; facturas con pagos o notas activas no se editan ni anulan.
- [x] Reportes, cartera, saldos de caja/banco y flujo de caja excluyen documentos anulados.
- [x] Pantallas sin ids internos: selector de cuentas PUC, productos, bodegas, terceros; listas desplegables en catálogos; costo promedio protegido; duplicados devuelven mensaje claro.
- [x] Navegación por módulos con subpantalla de opciones y ruta de migas; exógena y libros oficiales dentro de Reportes › Fiscales / Contables; páginas de reportes duplicadas eliminadas.
- [x] **Parametrización contable** (`backend/core/parametros.py`): Configuración › Parámetros contables define la cuenta de cada asiento automático (clientes, ingresos, devoluciones, IVA, costo, inventario, mercancía por facturar, faltantes/sobrantes, proveedores, retenciones, gasto de compras, caja y bancos). Cada producto puede tener cuentas propias de ingreso, inventario y costo; cada caja y banco tiene su cuenta contable. Se validan contra el plan de cuentas.
- [x] Libro, kardex y tesorería alineados: la entrada de mercancía contabiliza (inventario / mercancía por facturar) y la factura de proveedor cruza esa cuenta; los ajustes de inventario contabilizan faltantes y sobrantes; el POS entra a una caja concreta y suma a su saldo; los cobros/pagos cruzan contra la cuenta con que se contabilizó la factura. Cada empresa nueva trae una "Caja general".
- [x] **Motor de impuestos** (`backend/core/impuestos.py`): el perfil tributario de la empresa (régimen, responsable de IVA, gran contribuyente, agente de retención de renta/ICA y de IVA, autorretenedor, tarifa de ICA) define qué se puede parametrizar y aplicar; el perfil del tercero (régimen, responsable de IVA, declarante, autorretenedor, agente retenedor/ReteIVA) define qué retenciones se aplican en cada documento. Reglas del régimen SIMPLE según el art. 911 ET (sin retención en la fuente en ventas ni compras; sí ReteIVA). Productos con tipo de IVA (gravado/excluido/exento), concepto de retención en ventas y en compras y ReteICA, validados contra el perfil. Catálogo de conceptos de retención por empresa (Configuración › Conceptos de retención) con sugeridos. Ventas: IVA por perfil y producto, retenciones sufridas (cobro neto), autorretención con asiento. Compras: retenciones automáticas por línea con cuantías mínimas en UVT y previsualización en vivo; IVA no descontable para no responsables.
- [x] Notas crédito y débito prorratean retenciones sufridas, autorretención e impuesto al consumo de la factura origen; el saldo de la factura se ajusta por el neto.
- [x] **Impuesto al consumo (INC)**: cada impuesto con su tarifa y su cuenta contable; el producto lo referencia y se causa con la factura y el POS (y se revierte en notas).
- [x] Conceptos de retención con cuenta propia (pasivo y a favor); se usa en compras y ventas.
- [x] Saldo inicial de cajas y bancos con su propio asiento (contrapartida parametrizable); la cuenta contable de una caja o banco con movimientos no se puede cambiar.
- [x] Reportes fiscales: Impuestos y retenciones reescrito (IVA, INC, retenciones practicadas y sufridas, autorretenciones); Formulario 350 con autorretención y retención laboral; exógena 1003 con las retenciones que te practican.
- [x] Plan de cuentas: botón y endpoint para completar con las cuentas sugeridas en empresas existentes.
- [x] Pruebas automatizadas (48 en total) del ciclo de documentos, parametrización, impuestos, notas y nómina.

- [x] **Cierre de periodos**: Contabilidad › Cierre de periodos fija la fecha de cierre; ningún asiento puede crearse, editarse ni anularse en un periodo cerrado (control en el punto único de asientos).
- [x] **Redondeo exacto** al centavo (`core/dinero.py`) en todos los cálculos y cuadre en centavos.
- [x] **Vista imprimible** (carta) de cada documento desde su listado: facturas, notas, comprobantes, recibos, egresos, órdenes, entradas, ajustes y movimientos.
- [x] **Exportar a Excel** cualquier listado y **importar desde Excel/CSV** terceros, productos y saldos iniciales (plantilla, validación previa y carga todo-o-nada).
- [x] Listados con búsqueda y paginación; edición de usuarios (rol, permisos por módulo, empresas, activar/inactivar), restablecimiento de contraseña por el administrador y «Mi cuenta» para cambiar la propia; menú lateral adaptable a celulares.
- [x] Pruebas automatizadas: 65 en verde.

**Pendiente:**

- [ ] Modelos Pydantic por recurso en los catálogos (hoy CRUD genérico con `dict`).
- [ ] Filtros y paginación del lado del servidor cuando los volúmenes lo exijan (hoy búsqueda y paginación en el cliente).
- [ ] Balance de prueba, libro diario/mayor y estados financieros validados con casos de un contador (revisión a cargo del propietario).

## Fase 2 — Funcionalidad general y detalle por módulo · ⚪ siguiente

Primero se completa la funcionalidad general de cada módulo; después se revisa módulo por módulo en detalle (flujos, validaciones, reportes, casos reales).

### Compras, tesorería e impuestos

Hecho:

- [x] **Cartera por edades** (Tesorería › Antigüedad de cartera) por cobrar y por pagar, con fecha de corte, y **estado de cuenta por tercero** (facturas, pagos y saldo), imprimible y exportable.
- [x] **Devoluciones**: la nota crédito puede reingresar mercancía a la bodega al costo con que salió en la venta (inventario / costo de venta), valida que no se devuelva más de lo vendido y se revierte al editar o anular.
- [x] **Formulario 300 (IVA)** reescrito: ventas por tarifa netas de notas crédito/débito, IVA descontable, ReteIVA sufrida y saldo a pagar o a favor.
- [x] Dígito de verificación del NIT: se calcula y se valida en terceros y en la importación.
- [x] Selector de cuentas con búsqueda por código o nombre.
- [x] **Anticipos** de clientes (AC) y a proveedores (AD) con su aplicación a facturas (AA, sin mover efectivo), cuentas parametrizables (2805 / 1330), anulables; el estado de cuenta los muestra.
- [x] **Cobro o pago de varias facturas** de un tercero en una sola operación (todo o nada) y **transferencias** entre cajas y bancos (TR), que no cuentan como ingreso ni egreso en el flujo de caja.
- [x] **Régimen SIMPLE**: Formulario 2593 (anticipo bimestral) y 260 (declaración anual) calculados sobre los ingresos del libro, con tarifas por grupo de actividad editables por empresa (Configuración › Tarifas SIMPLE) y marca de «verificadas por el contador»; el descuento por aportes a pensión sale de la nómina.
- [x] **Órdenes de compra con seguimiento**: estados abierta, parcial, recibida, facturada y cerrada; las entradas no pueden superar lo pendiente y la factura de proveedor solo cubre lo recibido de la orden.
- [x] **Devoluciones a proveedor** (NP): reducen la deuda, sacan la mercancía del inventario y revierten el IVA descontable y las retenciones en la misma proporción.
- [x] **Costo de venta retroactivo**: el costo sale del kardex valorado a la fecha del documento y, si una compra con fecha anterior o una edición cambia el costo promedio, queda un asiento de ajuste por la diferencia (se limpia al anular).
- [x] **Facturas electrónicas recibidas**: carga del XML UBL 2.1 (o AttachedDocument) con CUFE único, validación del adquirente, eventos RADIAN (030, 031, 032, 033) con su secuencia, y contabilización como factura de proveedor ligada al CUFE. Los eventos quedan «pendientes de transmisión» hasta conectar el proveedor tecnológico.
- [x] Pruebas automatizadas: 83 en verde.

Pendiente:

- [ ] Ajustes de inventario (faltantes) valorados por fecha como las ventas, y devoluciones a proveedor al costo promedio de la fecha.
- [ ] Validar la lectura del XML con facturas reales de distintos proveedores (descuentos, cargos, retenciones en el XML, notas crédito recibidas) y la firma electrónica.
- [ ] Eventos RADIAN: aceptación tácita, endoso y transmisión (depende de la capa de Alegra).

## Fase 3 — Capa de integración con Alegra (penúltima tarea) · ⚪ pendiente

Objetivo: dejar el software listo para transmitir documentos electrónicos, de modo que solo falte conectar el contrato real de la API. Se construye con un **proveedor simulado y claramente rotulado** para poder probar todo el ciclo.

- [ ] Contrato canónico de documentos (factura, notas crédito/débito, documento soporte, nómina electrónica consolidada) independiente del proveedor, con interfaz `ClientePT`.
- [ ] Credenciales por empresa cifradas y pantalla «Conectar con Alegra» (probar conexión, ambiente de pruebas / producción).
- [ ] Sincronización de clientes, productos e impuestos con mapeo de identificadores (`alegra_id`).
- [ ] Numeraciones y resoluciones tomadas del proveedor para los documentos electrónicos.
- [ ] Cola de envío (outbox) con reintentos, idempotencia y estados (borrador, en cola, enviado, aceptado, rechazado).
- [ ] Webhook autenticado y consulta de estado; guarda CUFE/CUNE, XML y PDF; bitácora de intercambios.
- [ ] Bloqueo de edición y anulación de lo ya enviado (se corrige con nota crédito/débito o nota de ajuste).
- [ ] Notas de ajuste de nómina electrónica y validación contra el anexo técnico vigente.
- [ ] Pruebas en el ambiente de pruebas del proveedor antes de producción; confirmar con Alegra su API de emisión (incluida nómina).

## Fase 4 — Agentes dentro del software vía MCP (última tarea) · ⚪ pendiente

Objetivo: que agentes de IA operen como **auxiliar operativo** del contador, con los mismos permisos que el usuario que los invoca.

- [ ] Servidor MCP propio que expone herramientas de la API: consultas (saldos, cartera, kardex, impuestos del periodo), borradores de documentos y reportes.
- [ ] Autenticación por usuario y empresa: el agente hereda los permisos del usuario; sin atajos de administrador.
- [ ] Toda escritura queda como **borrador o propuesta** y exige confirmación humana antes de contabilizar.
- [ ] Bitácora de auditoría de las acciones del agente (qué pidió, qué herramienta, qué resultado).
- [ ] Límites de uso, protección contra instrucciones inyectadas en datos (terceros, descripciones) y modo de solo lectura.
- [ ] Casos de uso iniciales: conciliar movimientos, detectar descuadres, preparar el cierre del periodo, redactar el borrador de declaraciones, responder preguntas sobre el estado del negocio.

## Nómina y nómina electrónica · 🟡 núcleo construido

Decisiones: transmisión con **Alegra**; el cliente puede pagar **mensual o quincenal**, pero la nómina electrónica se envía **consolidada por mes y por empleado**.

Hecho (módulo Nómina):

- [x] Empleados (contrato, salario, afiliaciones, datos de pago, deducciones de retención) y novedades (horas extra y recargos, incapacidades, licencias, vacaciones, comisiones, bonificaciones, préstamos, embargos, libranzas).
- [x] Parámetros por año editables (SMMLV, auxilio, UVT, divisor de horas, recargos, aportes, ARL, FSP, tabla art. 383), con marca de "verificado".
- [x] Liquidación mensual o quincenal con su asiento: devengados, auxilio de transporte, IBC, salud, pensión, fondo de solidaridad, retención en la fuente laboral (procedimiento 1; en quincenal se practica en la segunda sobre lo acumulado), aportes del empleador con exoneración del art. 114-1, parafiscales y provisiones de cesantías, intereses, prima y vacaciones. Se puede recalcular y anular; desprendible imprimible.
- [x] Incapacidades: los 2 primeros días a cargo del empleador y el resto por cobrar a la EPS/ARL (cuenta parametrizable).
- [x] Pago de nómina contra caja o banco (egreso + asiento), anulable.
- [x] Pago de prima, cesantías, intereses y vacaciones contra lo provisionado por empleado; pago de seguridad social con el soporte PILA del mes (y CSV).
- [x] Liquidación de contrato: cesantías, intereses, prima, vacaciones, salario pendiente e indemnización (art. 64 CST); cancela provisiones y reconoce la diferencia; retira al empleado; anulable.
- [x] Paquete de **nómina electrónica mensual consolidado** por empleado con la estructura del anexo técnico (devengados, deducciones, fechas de pago, periodo, trabajador, empleador); exige liquidaciones pagadas; se puede ver y descargar.
- [x] Permisos por rol para el módulo (los usuarios existentes heredan la plantilla de su rol).
- [x] Retención laboral incluida en el Formulario 350.

Pendiente:

- [ ] **Transmisión real a la DIAN vía Alegra**: no hay documentación pública de su API de emisión de nómina; falta confirmarla con Alegra (o con su soporte), credenciales por empresa cifradas, consulta de estado, CUNE, XML y PDF, y **notas de ajuste** de nómina electrónica. Hoy responde 501 con un mensaje claro y deja el paquete listo.
- [ ] Validar la estructura del paquete contra el anexo técnico vigente de la DIAN (nombres y códigos de campos).
- [ ] Archivo plano de la PILA en el formato del operador de información (hoy: soporte en pantalla y CSV).
- [ ] Liquidación final con aportes y retención sobre el salario pendiente y retención sobre prestaciones.
- [ ] Procedimiento 2 de retención; historial de cambios de salario; promedio automático de variables para prestaciones.
- [ ] Módulo de vacaciones (programación y saldo de días por empleado), prórrogas automáticas de incapacidades y dotación.
- [ ] Certificado de ingresos y retenciones (formato 220), exógena 2276, certificado laboral.
- [ ] Reportes de nómina (costo por empleado y por periodo) y centros de costo.
- [ ] Consignación de cesantías al fondo con archivo de cargue; préstamos a empleados con su asiento de desembolso.
- [ ] Contratos especiales (aprendices, tiempo parcial con cotización especial, pensionados).
- [ ] Revisión de las cifras y reglas por un contador laboralista antes de operar con datos reales.

### Revisión módulo por módulo

**Contabilidad** (observaciones del propietario, 2026-10-13):

- [x] Tercero por línea en los comprobantes (por defecto el del encabezado, modificable).
- [x] Impresión con «Elaboró» y «Aprobó» (nombre del usuario) en todos los documentos.
- [x] **Aprobación**: rol «Auxiliar contable» (o marca «requiere aprobación» por usuario); sus comprobantes quedan «por aprobar» sin afectar el libro hasta que un administrador, un contador o quien tenga el permiso «Aprobar» los apruebe o rechace con motivo.
- [x] Cierre de periodos con el estado de cada mes y año (abierto, cerrado, parcial, futuro), documentos y pendientes por mes.
- [x] Consulta de comprobantes de **todos los módulos** (ventas, compras, cartera, tesorería, inventario, nómina…) con su comprobante contable, terceros, quién lo elaboró y aprobó, e impresión.
- [x] **Saldos iniciales de cartera**: la apertura (manual o importada) detalla clientes y proveedores por tercero, documento, fecha y vencimiento; quedan como CxC y CxP en Tesorería, antigüedad, estado de cuenta, reportes y exógena, y se pueden cobrar o pagar.
- [x] Comprobante de cierre: trae los saldos de las cuentas de resultado del periodo, sugiere el asiento contra la utilidad (3605) o pérdida (3610) y permite editarlo.
- [x] Auditoría con tipo de documento, comprobante, acción y usuario, con filtros.

- [x] **Aprobación en todos los módulos**: la petición de un usuario que requiere aprobación (crear, editar o anular facturas, POS, notas, compras, devoluciones, tesorería, anticipos, ajustes de inventario y nómina) queda como solicitud; quien tenga el permiso «Aprobar» del módulo la autoriza (se ejecuta a nombre del solicitante, con el aprobador en la auditoría y en la impresión) o la rechaza con motivo. Pantalla Aprobaciones y aviso en la barra superior.

Pendiente de la revisión de Contabilidad: incluir en la consulta los documentos anulados de todos los módulos.

**Configuración** (observaciones del propietario, 2026-10-13):

- [x] **Roles y permisos**: el acceso depende del rol y se edita en Configuración › Roles y permisos (matriz por módulo con Ver, Crear, Editar, Anular y Aprobar, y la marca «requiere aprobación»); se pueden crear roles propios. Los usuarios ya no tienen permisos individuales: al crear o editar solo eligen el rol.
- [x] Actividad económica (CIIU) elegida de una lista de la DIAN con búsqueda.
- [x] Plan de cuentas abierto por defecto hasta el detalle de 6 dígitos (subcuentas auxiliares en el PUC semilla y selector de nivel).
- [x] Las cuentas se definen donde nace cada cosa: el producto lleva sus cuentas de ingreso, inventario y costo (y sus retenciones) desde su creación; el empleado, sus cuentas de gasto de nómina; la caja y el banco, la suya. «Parámetros contables» pasa a ser «Cuentas por defecto» (respaldo y cuentas comunes).
- [x] Impuesto al consumo: un solo impuesto con varias tarifas y una cuenta única; el ICA queda aparte.
- [x] Resoluciones DIAN listas para sincronizar con el portal (tipo de documento, fecha, clave técnica, origen y botón «Sincronizar con la DIAN», que responde que falta el proveedor tecnológico hasta la capa de Alegra).

### Valor agregado

- [ ] Exógena, Formulario 350, libros oficiales.
- [ ] Conciliación bancaria con archivos de bancos (CSV/OFX).
- [ ] Calendario tributario con el decreto anual y festivos.
- [ ] Alertas de vencimientos (job programado).
- [ ] Sincronización con POS y tiendas online (definir plataformas).
- [ ] Revisión de detalle módulo por módulo: configuración, contabilidad, facturación, inventario, compras, tesorería, nómina y reportes.

## Deuda técnica y hallazgos de usabilidad

Detectados en las revisiones; se resuelven en la fase indicada.

- La factura de proveedor no ingresa mercancía por sí sola: para que el kardex suba se registra la entrada de mercancía. Evaluar una opción "ingresar a bodega" en la misma factura para comercios pequeños → Fase 1.
- ICA propio: se causa manualmente con un comprobante contable (decisión del cliente) → sin cambios.
- Exógena 2276 (rentas de trabajo) y certificados de ingresos y retenciones salen de nómina → Nómina.
- Los conceptos de retención sugeridos y la UVT deben revisarse cada año con el contador → recurrente.
- Cuentas por cobrar/pagar por tercero (p. ej. clientes del exterior) y cuentas por bodega aún no son parametrizables → Fase 1.
- Calendario tributario sin festivos (`FESTIVOS_CO` vacío) → Fase 4.
- Los reportes (balances, libros) aún no tienen botón propio de exportación; los listados sí → Fase 2.

## Bitácora

- **2026-10-12** — Se retoma el proyecto. Decisiones: MongoDB, Alegra, Easypanel. Fase 0: limpieza completa, dependencias actualizadas, autenticación por cookie, aislamiento multiempresa, alta de empresa transaccional con PUC, infraestructura Docker y pruebas escritas. Docker Desktop local reparado (socket `sailor-ingest.sock` bloqueado). Pruebas 11/11 en verde y stack de producción verificado en navegador; se corrigió un bug del selector de empresa tras el registro.
- **2026-10-12 (tarde)** — Revisión de usabilidad a pedido del usuario: navegación por módulos con subpantallas; reportes fiscales agrupados; numeración automática y editar/duplicar/anular en todos los documentos con un motor común; libro único; kardex recalculable; venta con costo e inventario; selectores en lugar de ids. 18 pruebas en verde y flujos verificados en navegador (comprobante crear/editar/duplicar/anular; entrada → factura → edición → kardex).
- **2026-10-12 (noche)** — Parametrización contable por empresa, producto, caja y banco; entrada de mercancía, ajustes de inventario y POS integrados al libro y a tesorería. 23 pruebas en verde; pantallas verificadas en navegador.
- **2026-10-12 (noche, 2)** — Motor de impuestos por perfil tributario (empresa, tercero, producto): IVA, retenciones sufridas y practicadas, autorretención, SIMPLE según art. 911 ET. 31 pruebas en verde; verificado en el navegador el cambio SIMPLE → ordinario sobre el formulario de producto. Nómina y nómina electrónica quedan planificadas (alcance y decisiones pendientes en el ROADMAP).
- **2026-10-13** — Impuestos completados (notas con retenciones prorrateadas, INC con su cuenta, reportes fiscales, saldos iniciales contabilizados, cuentas por concepto) y módulo de **nómina** (empleados, novedades, liquidación mensual/quincenal con asiento, pagos, prestaciones, PILA, liquidación de contrato, paquete mensual consolidado de nómina electrónica; transmisión a Alegra pendiente de su API). 48 pruebas en verde; flujo verificado en el navegador.
- **2026-10-13 (cierre de la Fase 0)** — Límite de intentos de login, respaldo con restauración verificada, CI, CSP/HSTS y cambio de contraseña; cierre de periodos; redondeo exacto al centavo; vista imprimible, exportación e importación Excel, búsqueda y paginación, administración de usuarios y menú móvil. 65 pruebas en verde. Cambio de decisión: dinero con redondeo al centavo en lugar de `Decimal128`; paginación en el cliente por ahora. Orden acordado: funcionalidad general → detalle por módulo → capa de Alegra → agentes MCP. La revisión contable la hace el propietario.
- **2026-10-13 (Fase 2, primer bloque)** — Cartera por edades y estado de cuenta, devoluciones con reingreso a inventario, Formulario 300 reescrito, DV del NIT y selector de cuentas con búsqueda. 70 pruebas en verde.
- **2026-10-13 (Fase 2, segundo bloque)** — Anticipos, cobros y pagos múltiples, transferencias, formularios SIMPLE 2593 y 260 con tarifas editables, seguimiento de órdenes de compra, devoluciones a proveedor, ajuste retroactivo del costo de venta y facturas electrónicas recibidas con eventos RADIAN. 83 pruebas en verde. Las tarifas SIMPLE son de referencia y requieren verificación del contador.
- **2026-10-13 (revisión de Contabilidad)** — Tercero por línea, firmas de elaboró y aprobó, flujo de aprobación para el auxiliar, estado de periodos, consulta unificada de todos los módulos, cartera inicial por documento, cierre sugerido y auditoría con usuario y acción.
- **2026-10-13 (revisión de Configuración y aprobación general)** — Aprobación para todos los módulos con solicitudes que se ejecutan al autorizar, roles y permisos editables, CIIU en lista, plan de cuentas a 6 dígitos, cuentas por producto y por empleado, INC único y resoluciones DIAN listas para sincronizar. 97 pruebas en verde.
