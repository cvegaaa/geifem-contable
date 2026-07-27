# Base de datos — GEIFEM Contable (MongoDB)

Toda la base es **multi-tenant**: casi todas las colecciones incluyen
`empresa_id` y quedan indexadas por ese campo. El borrado es lógico
(`activo: false`) salvo en colecciones de auditoría o movimientos históricos.

## Scripts

```bash
export MONGO_URI="mongodb+srv://..."
export DB_NAME="geifem_contable"
python init_indexes.py
```

## Colecciones

### empresas
Tenant raíz. Un documento por comerciante.
```
{ nit, razon_social, regimen_tributario ("SIMPLE"|"COMUN"),
  rango_numeracion_dian, pt_config, ciudad, actividad_ciiu, logo_url, activo }
```

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
PUC por empresa (semilla inicial según régimen desde `core/puc/seed.py`).
```
{ empresa_id, codigo, nombre, naturaleza ("debito"|"credito"),
  nivel, cuenta_padre_id, activo }
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
  costo_promedio_ponderado, existencia, activo }
```

### movimientos_inventario
```
{ empresa_id, producto_id, tipo ("entrada"|"salida"|"ajuste"),
  cantidad, costo_unitario, fecha, referencia_documento }
```

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
{ comprobante_id, usuario_id, accion ("creado"|"editado"|"borrado"),
  fecha_hora, detalle }
```

Colecciones adicionales previstas para Fases 2/3
(`ordenes_compra`, `facturas_proveedor`, `movimientos_tesoreria`,
`conciliaciones_bancarias`, `documentos_pos`, `notas_credito_debito`, `cxc`, `cxp`)
se documentarán al implementarse.
