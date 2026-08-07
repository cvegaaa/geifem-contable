"""Reportes — catálogo por categorías.

Estructura de categorías (coherente con la UI):
  ventas / administrativos / financieros / contables / fiscales /
  para-trabajar / exogena

Endpoints:
  GET /api/reportes/catalogo                      -> catálogo navegable
  GET /api/reportes/{categoria}/{slug}?desde&hasta -> datos del reporte
  Se conservan las rutas legacy form-300-iva, form-260-simple y
  estados-financieros.

Todos los reportes reciben el rango (desde, hasta) desde el componente
compartido `selector-rango-fechas` del frontend.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.dependencies import get_empresa_activa, require_permiso
from db import get_db

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

CATALOGO = [
    {
        "slug": "ventas",
        "titulo": "Ventas",
        "descripcion": "Monitorea la distribución de tus ventas y obtén información para gestionar tus operaciones comerciales.",
        "reportes": [
            {"slug": "ventas-generales", "titulo": "Ventas generales", "descripcion": "Revisa el desempeño de tus ventas para crear estrategias comerciales.", "estado": "activo"},
            {"slug": "ventas-por-item", "titulo": "Ventas por ítem", "descripcion": "Consulta tus ventas detalladas por cada ítem o servicio.", "estado": "activo"},
            {"slug": "ventas-por-cliente", "titulo": "Ventas por cliente", "descripcion": "Conoce las ventas asociadas a cada uno de tus clientes.", "estado": "activo"},
            {"slug": "rentabilidad-por-item", "titulo": "Rentabilidad por ítem", "descripcion": "Conoce la utilidad que generan tus ítems inventariables.", "estado": "activo"},
            {"slug": "ventas-por-vendedor", "titulo": "Ventas por vendedor", "descripcion": "Revisa el resumen de las ventas asociadas a cada vendedor/a.", "estado": "fase2"},
            {"slug": "estado-cuenta-por-cliente", "titulo": "Estado de cuenta por cliente", "descripcion": "Revisa el detalle de las ventas asociadas a cada cliente.", "estado": "activo"},
            {"slug": "ventas-diarias", "titulo": "Ventas diarias", "descripcion": "Exporta tus ventas agrupadas por forma de pago y numeraciones.", "estado": "activo", "exporta": "Excel"},
        ],
    },
    {
        "slug": "administrativos",
        "titulo": "Administrativos",
        "descripcion": "Haz seguimiento a tus transacciones y obtén información para controlar la salud financiera de tu empresa.",
        "reportes": [
            {"slug": "cuentas-por-cobrar", "titulo": "Cuentas por cobrar", "descripcion": "Controla el vencimiento y cobro de tus facturas a crédito.", "estado": "activo"},
            {"slug": "cuentas-por-pagar", "titulo": "Cuentas por pagar", "descripcion": "Controla tus deudas registradas y pagos pendientes a proveedores.", "estado": "activo"},
            {"slug": "ingresos-y-gastos", "titulo": "Ingresos y gastos", "descripcion": "Conoce los valores asociados a tus cuentas de ingresos y egresos.", "estado": "activo"},
            {"slug": "valor-inventario", "titulo": "Valor de inventario", "descripcion": "Consulta el valor actual, cantidad y costo promedio de tu inventario.", "estado": "activo"},
            {"slug": "transacciones", "titulo": "Transacciones", "descripcion": "Consulta los movimientos de dinero registrados en tu contabilidad.", "estado": "activo"},
            {"slug": "compras", "titulo": "Compras", "descripcion": "Consulta las facturas de compra que tienes registradas en tu cuenta.", "estado": "activo"},
            {"slug": "reporte-anual", "titulo": "Reporte anual", "descripcion": "Conoce el rendimiento que ha tenido tu negocio en cada año.", "estado": "activo"},
        ],
    },
    {
        "slug": "financieros",
        "titulo": "Financieros",
        "descripcion": "Analiza los resultados financieros de tu empresa, incluyendo entradas y salidas de efectivo.",
        "reportes": [
            {"slug": "flujo-de-caja", "titulo": "Flujo de caja", "descripcion": "Revisa la evolución de tus movimientos de efectivo y conoce la liquidez de tu empresa.", "estado": "activo"},
        ],
    },
    {
        "slug": "contables",
        "titulo": "Contables",
        "descripcion": "Conoce el desempeño contable y el estado económico de tu empresa en todo momento.",
        "reportes": [
            {"slug": "estado-de-resultados", "titulo": "Estado de resultados", "descripcion": "Conoce el desempeño financiero de tu empresa.", "estado": "activo"},
            {"slug": "estado-situacion-financiera", "titulo": "Estado de situación financiera", "descripcion": "Conoce los recursos que tienes y cómo se están aprovechando.", "estado": "activo"},
            {"slug": "movimientos-por-cuenta-contable", "titulo": "Movimientos por cuenta contable", "descripcion": "Conoce la actividad de tus cuentas y sus movimientos asociados.", "estado": "activo"},
            {"slug": "libro-diario", "titulo": "Libro diario", "descripcion": "Gestiona el movimiento contable de tus transacciones registradas.", "estado": "activo"},
            {"slug": "auxiliar-por-tercero", "titulo": "Auxiliar por tercero", "descripcion": "Consulta el saldo acumulado de tus cuentas por cada contacto.", "estado": "activo"},
            {"slug": "balance-de-prueba", "titulo": "Balance de prueba", "descripcion": "Consulta el saldo acumulado y los movimientos de tus cuentas.", "estado": "activo"},
            {"slug": "balance-de-prueba-por-tercero", "titulo": "Balance de prueba por tercero", "descripcion": "Consulta los movimientos de tus cuentas detallados por contacto.", "estado": "activo", "exporta": "Excel"},
            {"slug": "libro-mayor-y-balances", "titulo": "Libro mayor y balances", "descripcion": "Consulta los movimientos y balances detallados de tus cuentas.", "estado": "activo", "exporta": "PDF + 1"},
        ],
    },
    {
        "slug": "fiscales",
        "titulo": "Fiscales",
        "descripcion": "Revisa el detalle de tus impuestos y retenciones para cumplir con tus obligaciones tributarias.",
        "reportes": [
            {"slug": "reporte-detallado-de-impuestos", "titulo": "Reporte detallado de impuestos", "descripcion": "Revisa el detalle de tus impuestos generados por cada transacción.", "estado": "activo"},
            {"slug": "impuestos-y-retenciones", "titulo": "Impuestos y retenciones", "descripcion": "Revisa los impuestos y retenciones asociados a tus ventas y compras.", "estado": "activo"},
            {"slug": "comprobante-informe-diario", "titulo": "Comprobante de informe diario", "descripcion": "Exporta el resumen de tus facturas registradas en tu punto de venta.", "estado": "activo", "exporta": "Excel"},
            {"slug": "form-300-iva", "titulo": "Formulario 300 — IVA", "descripcion": "Declaración bimestral/cuatrimestral del impuesto sobre las ventas.", "estado": "activo"},
            {"slug": "form-260-simple", "titulo": "Formulario 260 — SIMPLE", "descripcion": "Recibo electrónico del régimen simple de tributación.", "estado": "activo"},
            {"slug": "formulario-350", "titulo": "Formulario 350", "descripcion": "Declaración retenciones en la fuente.", "estado": "activo"},
        ],
    },
    {
        "slug": "para-trabajar",
        "titulo": "Para trabajar",
        "descripcion": "Exporta la información clave de tu negocio para realizar análisis adicionales.",
        "reportes": [
            {"slug": "exportar-facturas", "titulo": "Exportar facturas", "descripcion": "Descarga el listado detallado de tus documentos de venta.", "estado": "activo", "exporta": "Excel"},
            {"slug": "informe-contador", "titulo": "Informe contador", "descripcion": "Exporta la información detallada de tus ventas, gastos y más.", "estado": "activo", "exporta": "Excel"},
            {"slug": "informe-de-mandatos", "titulo": "Informe de mandatos", "descripcion": "Exporta el detalle de tus ventas que incluyen ingresos para terceros.", "estado": "fase3", "exporta": "Excel"},
        ],
    },
    {
        "slug": "exogena",
        "titulo": "Información exógena",
        "descripcion": "Gestiona tus formatos de información exógena para presentarlos ante la DIAN.",
        "reportes": [
            {"slug": "formato-1001", "titulo": "Formato 1001", "descripcion": "Pagos o abonos en cuenta y retenciones practicadas.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1003", "titulo": "Formato 1003", "descripcion": "Retenciones en la fuente que te practicaron.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1005", "titulo": "Formato 1005", "descripcion": "Impuesto a las ventas por pagar (descontable).", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1006", "titulo": "Formato 1006", "descripcion": "Impuesto a las ventas por pagar (generado) e impuesto al consumo.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1007", "titulo": "Formato 1007", "descripcion": "Ingresos recibidos en el año.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1008", "titulo": "Formato 1008", "descripcion": "Saldo de cuentas por cobrar.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-1009", "titulo": "Formato 1009", "descripcion": "Saldo de cuentas por pagar.", "estado": "fase3", "exporta": "Excel"},
            {"slug": "formato-2276", "titulo": "Formato 2276", "descripcion": "Información de ingresos y retenciones por renta de trabajo y pensiones.", "estado": "fase3", "exporta": "Excel"},
        ],
    },
]


@router.get("/catalogo")
async def catalogo(_=Depends(require_permiso("reportes", "leer"))):
    return CATALOGO


# ---------------------------------------------------------------------------
# Helpers de datos
# ---------------------------------------------------------------------------

async def _facturas(empresa_id: str, desde: str, hasta: str):
    db = get_db()
    cursor = db.facturas.find({"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}})
    return [d async for d in cursor]


async def _pos(empresa_id: str, desde: str, hasta: str):
    db = get_db()
    cursor = db.documentos_pos.find({"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}})
    return [d async for d in cursor]


async def _asientos(empresa_id: str, desde: str, hasta: str):
    db = get_db()
    cursor = db.asientos_contables.find({"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}})
    return [d async for d in cursor]


async def _mapa_cuentas(empresa_id: str):
    db = get_db()
    return {
        str(c["_id"]): {"codigo": c.get("codigo", ""), "nombre": c.get("nombre", "")}
        async for c in db.plan_cuentas.find({"empresa_id": empresa_id})
    }


async def _mapa_terceros(empresa_id: str):
    db = get_db()
    return {
        str(t["_id"]): t.get("nombre", "")
        async for t in db.terceros.find({"empresa_id": empresa_id})
    }


async def _mapa_productos(empresa_id: str):
    db = get_db()
    return {
        str(p["_id"]): p
        async for p in db.catalogo_productos.find({"empresa_id": empresa_id})
    }


def _tabla(columnas, filas, resumen=None):
    return {"columnas": columnas, "filas": filas, "resumen": resumen or {}}


# ---------------------------------------------------------------------------
# Generadores por reporte
# ---------------------------------------------------------------------------

async def r_ventas_generales(empresa_id, desde, hasta):
    docs = await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta)
    por_dia = defaultdict(lambda: {"documentos": 0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in docs:
        b = por_dia[d.get("fecha", "")]
        b["documentos"] += 1
        b["subtotal"] += d.get("subtotal", 0)
        b["iva"] += d.get("iva_total", 0)
        b["total"] += d.get("total", 0)
    filas = [{"fecha": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
             for k, v in sorted(por_dia.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documentos", "label": "Documentos"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas,
        {"documentos": len(docs),
         "subtotal": round(sum(d.get("subtotal", 0) for d in docs), 2),
         "iva": round(sum(d.get("iva_total", 0) for d in docs), 2),
         "total": round(sum(d.get("total", 0) for d in docs), 2)},
    )


async def r_ventas_por_item(empresa_id, desde, hasta):
    productos = await _mapa_productos(empresa_id)
    acc = defaultdict(lambda: {"cantidad": 0.0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        for it in d.get("items", []):
            pid = it.get("producto_id") or it.get("descripcion", "—")
            a = acc[pid]
            a["cantidad"] += it.get("cantidad", 0)
            a["subtotal"] += it.get("subtotal", 0)
            a["iva"] += it.get("iva", 0)
            a["total"] += it.get("total", 0)
    filas = []
    for pid, a in acc.items():
        p = productos.get(pid)
        filas.append({"item": p.get("nombre") if p else pid, "sku": p.get("sku", "") if p else "",
                      **{k: round(v, 2) for k, v in a.items()}})
    filas.sort(key=lambda f: -f["total"])
    return _tabla(
        [{"key": "sku", "label": "SKU"}, {"key": "item", "label": "Ítem"},
         {"key": "cantidad", "label": "Cantidad"}, {"key": "subtotal", "label": "Subtotal"},
         {"key": "iva", "label": "IVA"}, {"key": "total", "label": "Total"}],
        filas, {"items": len(filas), "total": round(sum(f["total"] for f in filas), 2)},
    )


async def r_ventas_por_cliente(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta):
        a = acc[d.get("cliente_nombre") or "Sin cliente"]
        a["documentos"] += 1
        a["subtotal"] += d.get("subtotal", 0)
        a["iva"] += d.get("iva_total", 0)
        a["total"] += d.get("total", 0)
    filas = [{"cliente": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
             for k, v in sorted(acc.items(), key=lambda x: -x[1]["total"])]
    return _tabla(
        [{"key": "cliente", "label": "Cliente"}, {"key": "documentos", "label": "Documentos"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas, {"clientes": len(filas), "total": round(sum(f["total"] for f in filas), 2)},
    )


async def r_rentabilidad_por_item(empresa_id, desde, hasta):
    productos = await _mapa_productos(empresa_id)
    acc = defaultdict(lambda: {"cantidad": 0.0, "ingreso": 0.0, "costo": 0.0})
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        for it in d.get("items", []):
            pid = it.get("producto_id")
            if not pid:
                continue
            a = acc[pid]
            cant = it.get("cantidad", 0)
            a["cantidad"] += cant
            a["ingreso"] += it.get("subtotal", 0)
            a["costo"] += cant * productos.get(pid, {}).get("costo_promedio_ponderado", 0)
    filas = []
    for pid, a in acc.items():
        utilidad = a["ingreso"] - a["costo"]
        margen = (utilidad / a["ingreso"] * 100) if a["ingreso"] else 0
        filas.append({
            "item": productos.get(pid, {}).get("nombre", pid),
            "cantidad": round(a["cantidad"], 2), "ingreso": round(a["ingreso"], 2),
            "costo": round(a["costo"], 2), "utilidad": round(utilidad, 2),
            "margen": f"{margen:.1f}%",
        })
    filas.sort(key=lambda f: -f["utilidad"])
    return _tabla(
        [{"key": "item", "label": "Ítem"}, {"key": "cantidad", "label": "Cantidad"},
         {"key": "ingreso", "label": "Ingreso"}, {"key": "costo", "label": "Costo"},
         {"key": "utilidad", "label": "Utilidad"}, {"key": "margen", "label": "Margen"}],
        filas, {"utilidad_total": round(sum(f["utilidad"] for f in filas), 2)},
    )


async def r_estado_cuenta_por_cliente(empresa_id, desde, hasta):
    terceros = await _mapa_terceros(empresa_id)
    filas = []
    for d in await _facturas(empresa_id, desde, hasta):
        filas.append({
            "fecha": d.get("fecha"),
            "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
            "cliente": d.get("cliente_nombre") or terceros.get(d.get("cliente_id", ""), ""),
            "total": round(d.get("total", 0), 2),
            "estado": d.get("estado_dian", "borrador"),
        })
    filas.sort(key=lambda f: (f["cliente"], f["fecha"] or ""))
    return _tabla(
        [{"key": "cliente", "label": "Cliente"}, {"key": "fecha", "label": "Fecha"},
         {"key": "documento", "label": "Documento"}, {"key": "total", "label": "Total"},
         {"key": "estado", "label": "Estado"}],
        filas, {"documentos": len(filas), "total": round(sum(f["total"] for f in filas), 2)},
    )


async def r_ventas_diarias(empresa_id, desde, hasta):
    db = get_db()
    formas = {str(f["_id"]): f.get("nombre", "") async for f in db.formas_pago.find({"empresa_id": empresa_id})}
    acc = defaultdict(lambda: {"documentos": 0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        clave = (d.get("fecha", ""), f"{d.get('prefijo','')}", formas.get(d.get("forma_pago_id") or "", "—"))
        a = acc[clave]
        a["documentos"] += 1
        a["total"] += d.get("total", 0)
    filas = [{"fecha": k[0], "numeracion": k[1], "forma_pago": k[2],
              "documentos": v["documentos"], "total": round(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "numeracion", "label": "Numeración"},
         {"key": "forma_pago", "label": "Forma de pago"},
         {"key": "documentos", "label": "Documentos"}, {"key": "total", "label": "Total"}],
        filas, {"total": round(sum(f["total"] for f in filas), 2)},
    )


async def r_cuentas_por_cobrar(empresa_id, desde, hasta):
    filas = []
    for d in await _facturas(empresa_id, desde, hasta):
        filas.append({
            "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
            "cliente": d.get("cliente_nombre", ""),
            "fecha": d.get("fecha"),
            "vencimiento": d.get("fecha_vencimiento", "—"),
            "total": round(d.get("total", 0), 2),
            "saldo": round(d.get("saldo_pendiente", d.get("total", 0)), 2),
        })
    return _tabla(
        [{"key": "documento", "label": "Documento"}, {"key": "cliente", "label": "Cliente"},
         {"key": "fecha", "label": "Fecha"}, {"key": "vencimiento", "label": "Vencimiento"},
         {"key": "total", "label": "Total"}, {"key": "saldo", "label": "Saldo"}],
        filas, {"cartera": round(sum(f["saldo"] for f in filas), 2)},
    )


async def r_ingresos_y_gastos(empresa_id, desde, hasta):
    cuentas = await _mapa_cuentas(empresa_id)
    acc = defaultdict(lambda: {"debito": 0.0, "credito": 0.0})
    for a in await _asientos(empresa_id, desde, hasta):
        info = cuentas.get(a.get("cuenta_puc_id", ""), {})
        codigo = info.get("codigo", "")
        if not codigo.startswith(("4", "5", "6", "7")):
            continue
        k = (codigo, info.get("nombre", ""))
        acc[k]["debito"] += a.get("debito", 0)
        acc[k]["credito"] += a.get("credito", 0)
    filas = []
    ingresos = gastos = 0.0
    for (codigo, nombre), v in sorted(acc.items()):
        if codigo.startswith("4"):
            valor = v["credito"] - v["debito"]
            tipo = "Ingreso"
            ingresos += valor
        else:
            valor = v["debito"] - v["credito"]
            tipo = "Gasto/Costo"
            gastos += valor
        filas.append({"codigo": codigo, "cuenta": nombre, "tipo": tipo, "valor": round(valor, 2)})
    return _tabla(
        [{"key": "codigo", "label": "Código"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "tipo", "label": "Tipo"}, {"key": "valor", "label": "Valor"}],
        filas, {"ingresos": round(ingresos, 2), "gastos": round(gastos, 2),
                "resultado": round(ingresos - gastos, 2)},
    )


async def r_valor_inventario(empresa_id, desde, hasta):
    db = get_db()
    productos = await _mapa_productos(empresa_id)
    bodegas = {str(b["_id"]): b.get("nombre", "") async for b in db.bodegas.find({"empresa_id": empresa_id})}
    filas = []
    async for e in db.existencias_por_bodega.find({"empresa_id": empresa_id}):
        p = productos.get(e.get("producto_id", ""), {})
        costo = p.get("costo_promedio_ponderado", 0)
        cant = e.get("cantidad", 0)
        filas.append({
            "producto": p.get("nombre", e.get("producto_id", "")),
            "sku": p.get("sku", ""),
            "bodega": bodegas.get(e.get("bodega_id", ""), e.get("bodega_id", "")),
            "cantidad": round(cant, 2), "costo_promedio": round(costo, 2),
            "valor": round(cant * costo, 2),
        })
    return _tabla(
        [{"key": "sku", "label": "SKU"}, {"key": "producto", "label": "Producto"},
         {"key": "bodega", "label": "Bodega"}, {"key": "cantidad", "label": "Cantidad"},
         {"key": "costo_promedio", "label": "Costo prom."}, {"key": "valor", "label": "Valor"}],
        filas, {"valor_total": round(sum(f["valor"] for f in filas), 2)},
    )


async def r_transacciones(empresa_id, desde, hasta):
    cuentas = await _mapa_cuentas(empresa_id)
    terceros = await _mapa_terceros(empresa_id)
    filas = [{
        "fecha": a.get("fecha"),
        "cuenta": cuentas.get(a.get("cuenta_puc_id", ""), {}).get("codigo", ""),
        "nombre_cuenta": cuentas.get(a.get("cuenta_puc_id", ""), {}).get("nombre", ""),
        "tercero": terceros.get(a.get("tercero_id") or "", ""),
        "referencia": a.get("referencia", ""),
        "debito": round(a.get("debito", 0), 2),
        "credito": round(a.get("credito", 0), 2),
    } for a in await _asientos(empresa_id, desde, hasta)]
    filas.sort(key=lambda f: (f["fecha"] or "", f["cuenta"]))
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "nombre_cuenta", "label": "Nombre"}, {"key": "tercero", "label": "Tercero"},
         {"key": "referencia", "label": "Referencia"}, {"key": "debito", "label": "Débito"},
         {"key": "credito", "label": "Crédito"}],
        filas, {"debitos": round(sum(f["debito"] for f in filas), 2),
                "creditos": round(sum(f["credito"] for f in filas), 2)},
    )


async def r_reporte_anual(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        mes = (d.get("fecha") or "")[:7]
        acc[mes]["documentos"] += 1
        acc[mes]["total"] += d.get("total", 0)
    filas = [{"periodo": k, "documentos": v["documentos"], "total": round(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "periodo", "label": "Periodo"}, {"key": "documentos", "label": "Documentos"},
         {"key": "total", "label": "Total"}],
        filas, {"total": round(sum(f["total"] for f in filas), 2)},
    )


async def _saldos_por_cuenta(empresa_id, desde, hasta):
    cuentas = await _mapa_cuentas(empresa_id)
    acc = defaultdict(lambda: {"debito": 0.0, "credito": 0.0})
    for a in await _asientos(empresa_id, desde, hasta):
        info = cuentas.get(a.get("cuenta_puc_id", ""), {})
        acc[(info.get("codigo", ""), info.get("nombre", ""))]["debito"] += a.get("debito", 0)
        acc[(info.get("codigo", ""), info.get("nombre", ""))]["credito"] += a.get("credito", 0)
    return acc


async def r_balance_de_prueba(empresa_id, desde, hasta):
    acc = await _saldos_por_cuenta(empresa_id, desde, hasta)
    filas = [{"codigo": c, "cuenta": n, "debito": round(v["debito"], 2),
              "credito": round(v["credito"], 2),
              "saldo": round(v["debito"] - v["credito"], 2)}
             for (c, n), v in sorted(acc.items())]
    return _tabla(
        [{"key": "codigo", "label": "Código"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "debito", "label": "Débito"}, {"key": "credito", "label": "Crédito"},
         {"key": "saldo", "label": "Saldo"}],
        filas, {"debitos": round(sum(f["debito"] for f in filas), 2),
                "creditos": round(sum(f["credito"] for f in filas), 2)},
    )


async def r_libro_mayor_y_balances(empresa_id, desde, hasta):
    return await r_balance_de_prueba(empresa_id, desde, hasta)


async def r_movimientos_por_cuenta(empresa_id, desde, hasta):
    return await r_transacciones(empresa_id, desde, hasta)


async def r_libro_diario(empresa_id, desde, hasta):
    return await r_transacciones(empresa_id, desde, hasta)


async def r_auxiliar_por_tercero(empresa_id, desde, hasta):
    cuentas = await _mapa_cuentas(empresa_id)
    terceros = await _mapa_terceros(empresa_id)
    acc = defaultdict(lambda: {"debito": 0.0, "credito": 0.0})
    for a in await _asientos(empresa_id, desde, hasta):
        info = cuentas.get(a.get("cuenta_puc_id", ""), {})
        k = (terceros.get(a.get("tercero_id") or "", "Sin tercero"), info.get("codigo", ""), info.get("nombre", ""))
        acc[k]["debito"] += a.get("debito", 0)
        acc[k]["credito"] += a.get("credito", 0)
    filas = [{"tercero": t, "codigo": c, "cuenta": n, "debito": round(v["debito"], 2),
              "credito": round(v["credito"], 2), "saldo": round(v["debito"] - v["credito"], 2)}
             for (t, c, n), v in sorted(acc.items())]
    return _tabla(
        [{"key": "tercero", "label": "Tercero"}, {"key": "codigo", "label": "Código"},
         {"key": "cuenta", "label": "Cuenta"}, {"key": "debito", "label": "Débito"},
         {"key": "credito", "label": "Crédito"}, {"key": "saldo", "label": "Saldo"}],
        filas,
    )


async def r_estado_de_resultados(empresa_id, desde, hasta):
    acc = await _saldos_por_cuenta(empresa_id, desde, hasta)
    filas = []
    ingresos = costos = gastos = 0.0
    for (codigo, nombre), v in sorted(acc.items()):
        if codigo.startswith("4"):
            valor = v["credito"] - v["debito"]
            ingresos += valor
            grupo = "Ingresos"
        elif codigo.startswith("6"):
            valor = v["debito"] - v["credito"]
            costos += valor
            grupo = "Costos"
        elif codigo.startswith(("5", "7")):
            valor = v["debito"] - v["credito"]
            gastos += valor
            grupo = "Gastos"
        else:
            continue
        filas.append({"grupo": grupo, "codigo": codigo, "cuenta": nombre, "valor": round(valor, 2)})
    return _tabla(
        [{"key": "grupo", "label": "Grupo"}, {"key": "codigo", "label": "Código"},
         {"key": "cuenta", "label": "Cuenta"}, {"key": "valor", "label": "Valor"}],
        filas, {"ingresos": round(ingresos, 2), "costos": round(costos, 2),
                "gastos": round(gastos, 2),
                "utilidad": round(ingresos - costos - gastos, 2)},
    )


async def r_estado_situacion_financiera(empresa_id, desde, hasta):
    acc = await _saldos_por_cuenta(empresa_id, desde, hasta)
    filas = []
    activo = pasivo = patrimonio = 0.0
    for (codigo, nombre), v in sorted(acc.items()):
        if codigo.startswith("1"):
            valor = v["debito"] - v["credito"]
            activo += valor
            grupo = "Activo"
        elif codigo.startswith("2"):
            valor = v["credito"] - v["debito"]
            pasivo += valor
            grupo = "Pasivo"
        elif codigo.startswith("3"):
            valor = v["credito"] - v["debito"]
            patrimonio += valor
            grupo = "Patrimonio"
        else:
            continue
        filas.append({"grupo": grupo, "codigo": codigo, "cuenta": nombre, "valor": round(valor, 2)})
    return _tabla(
        [{"key": "grupo", "label": "Grupo"}, {"key": "codigo", "label": "Código"},
         {"key": "cuenta", "label": "Cuenta"}, {"key": "valor", "label": "Valor"}],
        filas, {"activo": round(activo, 2), "pasivo": round(pasivo, 2),
                "patrimonio": round(patrimonio, 2)},
    )


async def r_form_300_iva(empresa_id, desde, hasta):
    docs = await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta)
    acc = defaultdict(lambda: {"base": 0.0, "iva": 0.0})
    for d in docs:
        for it in d.get("items", []):
            acc[it.get("tarifa_iva", 0)]["base"] += it.get("subtotal", 0)
            acc[it.get("tarifa_iva", 0)]["iva"] += it.get("iva", 0)
    filas = [{"tarifa": f"{t}%", "base": round(v["base"], 2), "iva": round(v["iva"], 2)}
             for t, v in sorted(acc.items())]
    return _tabla(
        [{"key": "tarifa", "label": "Tarifa"}, {"key": "base", "label": "Base gravable"},
         {"key": "iva", "label": "IVA generado"}],
        filas, {"base_gravable": round(sum(f["base"] for f in filas), 2),
                "iva_generado": round(sum(f["iva"] for f in filas), 2),
                "documentos": len(docs)},
    )


async def r_form_260_simple(empresa_id, desde, hasta):
    docs = await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta)
    acc = defaultdict(lambda: {"documentos": 0, "ingresos": 0.0})
    for d in docs:
        mes = (d.get("fecha") or "")[:7]
        acc[mes]["documentos"] += 1
        acc[mes]["ingresos"] += d.get("total", 0)
    filas = [{"periodo": k, "documentos": v["documentos"], "ingresos": round(v["ingresos"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "periodo", "label": "Periodo"}, {"key": "documentos", "label": "Documentos"},
         {"key": "ingresos", "label": "Ingresos brutos"}],
        filas, {"ingresos_brutos": round(sum(f["ingresos"] for f in filas), 2)},
    )


async def r_reporte_detallado_impuestos(empresa_id, desde, hasta):
    filas = []
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        for it in d.get("items", []):
            filas.append({
                "fecha": d.get("fecha"),
                "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
                "impuesto": f"IVA {it.get('tarifa_iva', 0)}%",
                "base": round(it.get("subtotal", 0), 2),
                "valor": round(it.get("iva", 0), 2),
            })
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "impuesto", "label": "Impuesto"}, {"key": "base", "label": "Base"},
         {"key": "valor", "label": "Valor"}],
        filas, {"total_impuestos": round(sum(f["valor"] for f in filas), 2)},
    )


async def r_impuestos_y_retenciones(empresa_id, desde, hasta):
    tabla = await r_form_300_iva(empresa_id, desde, hasta)
    tabla["resumen"]["retenciones"] = "Pendiente Fase 2 (motor de retenciones)"
    return tabla


async def r_comprobante_informe_diario(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in await _pos(empresa_id, desde, hasta):
        a = acc[d.get("fecha", "")]
        a["documentos"] += 1
        a["subtotal"] += d.get("subtotal", 0)
        a["iva"] += d.get("iva_total", 0)
        a["total"] += d.get("total", 0)
    filas = [{"fecha": k, "documentos": v["documentos"], "subtotal": round(v["subtotal"], 2),
              "iva": round(v["iva"], 2), "total": round(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documentos", "label": "Documentos POS"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas, {"total": round(sum(f["total"] for f in filas), 2)},
    )


async def r_exportar_facturas(empresa_id, desde, hasta):
    filas = [{
        "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
        "fecha": d.get("fecha"), "cliente": d.get("cliente_nombre", ""),
        "subtotal": round(d.get("subtotal", 0), 2), "iva": round(d.get("iva_total", 0), 2),
        "total": round(d.get("total", 0), 2), "estado_dian": d.get("estado_dian", ""),
        "cufe": d.get("cufe") or "—",
    } for d in await _facturas(empresa_id, desde, hasta)]
    return _tabla(
        [{"key": "documento", "label": "Documento"}, {"key": "fecha", "label": "Fecha"},
         {"key": "cliente", "label": "Cliente"}, {"key": "subtotal", "label": "Subtotal"},
         {"key": "iva", "label": "IVA"}, {"key": "total", "label": "Total"},
         {"key": "estado_dian", "label": "Estado DIAN"}, {"key": "cufe", "label": "CUFE"}],
        filas, {"documentos": len(filas)},
    )


async def r_informe_contador(empresa_id, desde, hasta):
    ventas = await r_ventas_generales(empresa_id, desde, hasta)
    resultado = await r_estado_de_resultados(empresa_id, desde, hasta)
    return _tabla(resultado["columnas"], resultado["filas"],
                  {**resultado["resumen"], **{f"ventas_{k}": v for k, v in ventas["resumen"].items()}})


# ---------------------------------------------------------------------------
# Generadores FASE 2 (compras / tesorería)
# ---------------------------------------------------------------------------

async def _facturas_proveedor(empresa_id, desde, hasta):
    db = get_db()
    return [d async for d in db.facturas_proveedor.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}})]


async def r_cuentas_por_pagar(empresa_id, desde, hasta):
    db = get_db()
    filas = []
    async for f in db.facturas_proveedor.find({"empresa_id": empresa_id}).sort("fecha", 1):
        saldo = float(f.get("saldo_pendiente", f.get("total_a_pagar", 0)))
        if saldo <= 0.009:
            continue
        filas.append({
            "fecha": f.get("fecha"), "documento": f.get("numero_factura", ""),
            "proveedor": f.get("proveedor_nombre", ""),
            "vencimiento": f.get("fecha_vencimiento") or "",
            "total": f.get("total_a_pagar", 0), "saldo": round(saldo, 2),
        })
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "proveedor", "label": "Proveedor"}, {"key": "vencimiento", "label": "Vencimiento"},
         {"key": "total", "label": "Total"}, {"key": "saldo", "label": "Saldo"}],
        filas, {"saldo_total": round(sum(f["saldo"] for f in filas), 2),
                "documentos": len(filas)},
    )


async def r_compras(empresa_id, desde, hasta):
    filas = []
    for f in await _facturas_proveedor(empresa_id, desde, hasta):
        filas.append({
            "fecha": f.get("fecha"), "documento": f.get("numero_factura", ""),
            "proveedor": f.get("proveedor_nombre", ""),
            "subtotal": f.get("subtotal", 0), "iva": f.get("iva_total", 0),
            "retenciones": f.get("total_retenciones", 0),
            "total": f.get("total_a_pagar", f.get("total", 0)),
        })
    filas.sort(key=lambda x: x["fecha"] or "")
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "proveedor", "label": "Proveedor"}, {"key": "subtotal", "label": "Subtotal"},
         {"key": "iva", "label": "IVA"}, {"key": "retenciones", "label": "Retenciones"},
         {"key": "total", "label": "Neto"}],
        filas, {"subtotal": round(sum(f["subtotal"] for f in filas), 2),
                "iva": round(sum(f["iva"] for f in filas), 2),
                "total": round(sum(f["total"] for f in filas), 2),
                "documentos": len(filas)},
    )


async def r_flujo_de_caja(empresa_id, desde, hasta):
    db = get_db()
    por_dia = defaultdict(lambda: {"ingresos": 0.0, "egresos": 0.0})
    async for m in db.movimientos_tesoreria.find(
        {"empresa_id": empresa_id, "fecha": {"$gte": desde, "$lte": hasta}}
    ):
        clave = "ingresos" if m.get("tipo") == "ingreso" else "egresos"
        por_dia[m.get("fecha")][clave] += float(m.get("valor", 0))
    filas, acumulado = [], 0.0
    for fecha in sorted(k for k in por_dia if k):
        ing = round(por_dia[fecha]["ingresos"], 2)
        egr = round(por_dia[fecha]["egresos"], 2)
        acumulado += ing - egr
        filas.append({"fecha": fecha, "ingresos": ing, "egresos": egr,
                      "neto": round(ing - egr, 2), "acumulado": round(acumulado, 2)})
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "ingresos", "label": "Ingresos"},
         {"key": "egresos", "label": "Egresos"}, {"key": "neto", "label": "Neto"},
         {"key": "acumulado", "label": "Acumulado"}],
        filas, {"ingresos": round(sum(f["ingresos"] for f in filas), 2),
                "egresos": round(sum(f["egresos"] for f in filas), 2),
                "neto": round(acumulado, 2)},
    )


async def r_formulario_350(empresa_id, desde, hasta):
    """Retenciones en la fuente practicadas (base para el formulario 350)."""
    facturas = await _facturas_proveedor(empresa_id, desde, hasta)
    base = round(sum(f.get("subtotal", 0) for f in facturas), 2)
    rte = round(sum(f.get("retenciones", {}).get("retefuente", 0) for f in facturas), 2)
    ica = round(sum(f.get("retenciones", {}).get("reteica", 0) for f in facturas), 2)
    iva = round(sum(f.get("retenciones", {}).get("reteiva", 0) for f in facturas), 2)
    filas = [
        {"concepto": "Base sujeta a retención (compras)", "valor": base},
        {"concepto": "Retención en la fuente a título de renta", "valor": rte},
        {"concepto": "Retención de IVA (reteIVA)", "valor": iva},
        {"concepto": "Retención de ICA (reteICA)", "valor": ica},
        {"concepto": "Total retenciones a declarar", "valor": round(rte + iva + ica, 2)},
    ]
    return _tabla(
        [{"key": "concepto", "label": "Concepto"}, {"key": "valor", "label": "Valor"}],
        filas, {"base": base, "retefuente": rte, "reteiva": iva, "reteica": ica,
                "total": round(rte + iva + ica, 2)},
    )


GENERADORES = {
    ("ventas", "ventas-generales"): r_ventas_generales,
    ("ventas", "ventas-por-item"): r_ventas_por_item,
    ("ventas", "ventas-por-cliente"): r_ventas_por_cliente,
    ("ventas", "rentabilidad-por-item"): r_rentabilidad_por_item,
    ("ventas", "estado-cuenta-por-cliente"): r_estado_cuenta_por_cliente,
    ("ventas", "ventas-diarias"): r_ventas_diarias,
    ("administrativos", "cuentas-por-cobrar"): r_cuentas_por_cobrar,
    ("administrativos", "ingresos-y-gastos"): r_ingresos_y_gastos,
    ("administrativos", "valor-inventario"): r_valor_inventario,
    ("administrativos", "transacciones"): r_transacciones,
    ("administrativos", "reporte-anual"): r_reporte_anual,
    ("contables", "estado-de-resultados"): r_estado_de_resultados,
    ("contables", "estado-situacion-financiera"): r_estado_situacion_financiera,
    ("contables", "movimientos-por-cuenta-contable"): r_movimientos_por_cuenta,
    ("contables", "libro-diario"): r_libro_diario,
    ("contables", "auxiliar-por-tercero"): r_auxiliar_por_tercero,
    ("contables", "balance-de-prueba"): r_balance_de_prueba,
    ("contables", "balance-de-prueba-por-tercero"): r_auxiliar_por_tercero,
    ("contables", "libro-mayor-y-balances"): r_libro_mayor_y_balances,
    ("fiscales", "reporte-detallado-de-impuestos"): r_reporte_detallado_impuestos,
    ("fiscales", "impuestos-y-retenciones"): r_impuestos_y_retenciones,
    ("fiscales", "comprobante-informe-diario"): r_comprobante_informe_diario,
    ("fiscales", "form-300-iva"): r_form_300_iva,
    ("fiscales", "form-260-simple"): r_form_260_simple,
    ("administrativos", "cuentas-por-pagar"): r_cuentas_por_pagar,
    ("administrativos", "compras"): r_compras,
    ("financieros", "flujo-de-caja"): r_flujo_de_caja,
    ("fiscales", "formulario-350"): r_formulario_350,
    ("para-trabajar", "exportar-facturas"): r_exportar_facturas,
    ("para-trabajar", "informe-contador"): r_informe_contador,
}

FASE_PENDIENTE = {
    "fase2": "Módulo pendiente — Fase 2",
    "fase3": "Módulo pendiente — Fase 3",
}


def _buscar_meta(categoria: str, slug: str):
    for cat in CATALOGO:
        if cat["slug"] == categoria:
            for rep in cat["reportes"]:
                if rep["slug"] == slug:
                    return cat, rep
    return None, None


# ---------------------------------------------------------------------------
# Rutas legacy (compatibilidad Fase 1)
# ---------------------------------------------------------------------------

@router.get("/form-300-iva")
async def form_300_iva(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    return {"periodo": {"desde": desde, "hasta": hasta}, **await r_form_300_iva(empresa_id, desde, hasta)}


@router.get("/form-260-simple")
async def form_260_simple(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    return {"periodo": {"desde": desde, "hasta": hasta}, **await r_form_260_simple(empresa_id, desde, hasta)}


@router.get("/estados-financieros")
async def estados_financieros(
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    return {
        "periodo": {"desde": desde, "hasta": hasta},
        "estado_resultados": await r_estado_de_resultados(empresa_id, desde, hasta),
        "situacion_financiera": await r_estado_situacion_financiera(empresa_id, desde, hasta),
    }


# ---------------------------------------------------------------------------
# Libros oficiales — FASE 2 (folio consecutivo oficial)
# ---------------------------------------------------------------------------

LIBROS_OFICIALES = [
    {"slug": "diario", "titulo": "Libro diario"},
    {"slug": "mayor-y-balances", "titulo": "Libro mayor y balances"},
    {"slug": "inventarios-y-balances", "titulo": "Libro de inventarios y balances"},
]


@router.get("/libros-oficiales")
async def libros_oficiales(
    libro: str = Query("diario"),
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    """Libros oficiales con numeración consecutiva de folios."""
    meta = next((l for l in LIBROS_OFICIALES if l["slug"] == libro), None)
    if not meta:
        raise HTTPException(404, "Libro no encontrado")

    if libro == "diario":
        datos = await r_libro_diario(empresa_id, desde, hasta)
    elif libro == "mayor-y-balances":
        datos = await r_balance_de_prueba(empresa_id, desde, hasta)
    else:
        datos = await r_estado_situacion_financiera(empresa_id, desde, hasta)

    filas = [{"folio": i + 1, **f} for i, f in enumerate(datos["filas"])]
    columnas = [{"key": "folio", "label": "Folio"}] + datos["columnas"]
    return {
        "libro": meta["titulo"],
        "libros_disponibles": LIBROS_OFICIALES,
        "periodo": {"desde": desde, "hasta": hasta},
        "folios": len(filas),
        "columnas": columnas,
        "filas": filas,
        "resumen": datos.get("resumen", {}),
    }


# ---------------------------------------------------------------------------
# Ruta genérica por categoría/reporte
# ---------------------------------------------------------------------------

@router.get("/{categoria}/{slug}")
async def generar_reporte(
    categoria: str, slug: str,
    desde: str = Query(...), hasta: str = Query(...),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    cat, meta = _buscar_meta(categoria, slug)
    if not meta:
        raise HTTPException(404, "Reporte no encontrado")
    if meta["estado"] in FASE_PENDIENTE:
        raise HTTPException(501, f"{meta['titulo']} — {FASE_PENDIENTE[meta['estado']]}")
    generador = GENERADORES.get((categoria, slug))
    if not generador:
        raise HTTPException(501, f"{meta['titulo']} — Módulo pendiente")
    datos = await generador(empresa_id, desde, hasta)
    return {
        "categoria": cat["titulo"], "titulo": meta["titulo"],
        "descripcion": meta["descripcion"],
        "periodo": {"desde": desde, "hasta": hasta},
        **datos,
    }
