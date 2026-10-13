# Base de datos — GEIFEM Contable (MongoDB)

Toda la base es **multi-tenant**: casi todas las colecciones incluyen
`empresa_id` y quedan indexadas por ese campo. El borrado es lógico
(`activo: false`) salvo en colecciones de auditoría o movimientos históricos.

Los índices se definen en `backend/db/indices.py` y la API los aplica al arrancar.
Este documento se actualiza en la Fase 1 (libro contable único, `Decimal128`).

## Convenciones de documentos

Todo documento (comprobantes, facturas, POS, notas, órdenes, entradas, facturas
de proveedor, movimientos de tesorería, pagos, ajustes de inventario) tiene:

```
{ prefijo, consecutivo, numero ("CA-1", "FE15"…), estado (… | "anulado"),
  creado_por, fecha_creacion, editado_por?, fecha_actualizacion?,
  anulado_por?, fecha_anulacion?, motivo_anulacion? }
```

- `contadores { empresa_id, clave, valor }`: consecutivo atómico por empresa y tipo.
- `asientos_contables` y `movimientos_inventario` llevan `documento_tipo` +
  `documento_id`: así se revierten al editar o anular el documento.
- `auditoria { empresa_id, documento_tipo, documento_id, numero, usuario_id,
  accion ("creado"|"editado"|"anulado"), fecha_hora, detalle }`.
- Los documentos no se borran: se anulan (la numeración no puede tener huecos).

## Colecciones

### empresas
Tenant raíz. Un documento por comerciante.
```
{ nit (único), dv, razon_social, regimen_tributario ("ORDINARIO"|"SIMPLE"),
  responsable_iva (bool), ciudad, direccion, telefono, email, actividad_ciiu,
  activo, creado_por, fecha_creacion }
```
Al crearla (registro o "Nueva empresa") se generan en la misma transacción su
plan de cuentas semilla y la bodega "Principal", y se agrega a `empresa_ids`
del usuario creador.

### usuarios
Auth. Un usuario puede pertenecer a múltiples empresas.
```
{ email (único), nombre, password_hash, rol ("admin"|"contador"|"vendedor"),
  empresa_ids: [empresa_id], permisos: { modulo: [acciones] },
  activo, fecha_creacion }
```

### terceros
Clientes, proveedores y otros.
```
{ empresa_id, tipo ("cliente"|"proveedor"|"otro"),
  tipo_persona ("natural"|"juridica"),
  tipo_documento ("CC"|"NIT"|"CE"|"pasaporte"), numero_documento,
  nombre, datos_contacto, activo }
```

### plan_cuentas
PUC por empresa (semilla desde `core/puc/seed.py`, igual para ambos regímenes).
```
{ empresa_id, codigo, nombre, naturaleza ("debito"|"credito"),
  nivel, codigo_padre, acepta_movimientos, activo }
```

### tipos_documento
```
{ empresa_id, nombre, prefijo, consecutivo_actual, activo }
```

### resoluciones_dian
```
{ empresa_id, numero_resolucion, prefijo, rango_desde, rango_hasta,
  fecha_inicio, fecha_fin, tipo_documento_id, consecutivo_actual, activo }
```

### centros_costo
`{ empresa_id, codigo, nombre, activo }`

### impuestos_config
`{ empresa_id, tipo ("IVA"|"INC"|"ICA"|"retencion"), tarifa, base_minima, ciudad }`

### unidades_medida
`{ empresa_id, nombre, abreviatura, activo }`

### formas_pago
`{ empresa_id, nombre, tipo ("efectivo"|"transferencia"|"tarjeta"|"nequi"|"daviplata"), activo }`

### productos
```
{ empresa_id, sku, nombre, categoria, unidad_medida_id,
  costo_promedio_ponderado, activo }
```
La existencia ya no se guarda aquí (multi-bodega).

### bodegas
```
{ empresa_id, nombre, direccion, es_principal, activo }
```
Al crear una `empresa` se genera automáticamente una bodega "Principal".

### existencias_por_bodega
```
{ empresa_id, producto_id, bodega_id, cantidad, fecha_actualizacion }
```
Índice único `(empresa_id, producto_id, bodega_id)`.

### movimientos_inventario
```
{ empresa_id, producto_id, bodega_id, tipo ("entrada"|"salida"|"ajuste"|"traslado"),
  cantidad, costo_unitario, fecha, referencia_documento,
  bodega_destino_id? }
```
`traslado` está reservado para Fase 2.

### facturas
```
{ empresa_id, cliente_id, items, cufe, xml_url, pdf_url,
  estado_dian ("borrador"|"acuse"|"aceptado"|"rechazado"), fecha }
```

### asientos_contables
```
{ empresa_id, fecha, cuenta_puc_id, tercero_id, debito, credito, referencia }
```

### comprobantes_contables
```
{ empresa_id, tipo ("ajuste"|"nota"|"apertura"|"cierre"), fecha, consecutivo,
  tercero_id?, lineas: [{cuenta_puc_id, debito, credito}],
  estado ("borrador"|"contabilizado"), creado_por, fecha_creacion }
```

### auditoria_comprobantes
```
{ empresa_id, comprobante_id, usuario_id, accion ("creado"|"editado"|"borrado"),
  fecha_hora, detalle }
```

Colecciones adicionales previstas para Fases 2/3
(`ordenes_compra`, `facturas_proveedor`, `movimientos_tesoreria`,
`conciliaciones_bancarias`, `documentos_pos`, `notas_credito_debito`, `cxc`, `cxp`)
se documentarán al implementarse.

## Impuestos y nómina

- `conceptos_retencion { empresa_id, tipo (retefuente|reteica|reteiva), nombre, tarifa, tarifa_no_declarante?,
  base_uvt, cuenta_pasivo?, cuenta_favor? }`: catálogo de retenciones por empresa.
- `impuestos_config { tipo: "INC", nombre, tarifa, cuenta_contable }`: impuesto al consumo.
- `parametros_contables { empresa_id, cuentas: {clave: codigo} }`: cuentas por defecto de cada asiento automático.
- Productos: `tipo_iva`, `tarifa_iva`, `impuesto_consumo_id`, `concepto_retefuente_venta_id`,
  `concepto_retefuente_compra_id`, `aplica_reteica`, `cuenta_ingreso|inventario|costo`.
- Terceros: `regimen`, `responsable_iva`, `declarante_renta`, `autorretenedor`, `agente_retenedor`, `agente_reteiva`, `gran_contribuyente`.
- Empresas: perfil tributario (`responsable_iva`, `agente_retenedor`, `agente_reteiva`, `autorretenedor_renta`,
  `tarifa_autorretencion`, `tarifa_reteica`, `gran_contribuyente`).
- Facturas y notas: `retenciones`, `detalle_retenciones`, `autorretencion`, `inc_total`, `total_a_cobrar` / `neto`.
- Nómina: `empleados`, `nomina_novedades`, `nomina_parametros` (por año), `nomina_periodos` (con `lineas` por empleado y
  `totales`), `nomina_pagos`, `nomina_obligaciones` (libro de provisiones y pagos de prestaciones por empleado),
  `nomina_pagos_obligaciones`, `nomina_liquidaciones_finales`, `nomina_electronica` (paquete mensual por empleado).
