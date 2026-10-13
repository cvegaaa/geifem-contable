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
from datetime import date

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from core import cartera, simple
from core.auth.dependencies import get_empresa_activa, require_permiso
from core.documentos import NO_ANULADO
from db import get_db
from core.dinero import redondear
from core.retenciones import valor_uvt

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
            {"slug": "form-260-simple", "titulo": "Formulario 260 — SIMPLE anual", "descripcion": "Declaración anual consolidada del régimen SIMPLE de tributación.", "estado": "activo"},
            {"slug": "form-2593-simple", "titulo": "Formulario 2593 — SIMPLE bimestral", "descripcion": "Recibo electrónico SIMPLE: anticipo bimestral sobre los ingresos del bimestre.", "estado": "activo"},
            {"slug": "formulario-350", "titulo": "Formulario 350", "descripcion": "Declaración retenciones en la fuente.", "estado": "activo"},
            {"slug": "calendario-tributario", "titulo": "Calendario tributario", "descripcion": "Consulta las fechas límite de tus obligaciones fiscales según tu NIT y régimen.", "estado": "activo", "ruta": "/reportes/calendario-tributario"},
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
            {"slug": "formato-1001", "titulo": "Formato 1001", "descripcion": "Pagos o abonos en cuenta y retenciones practicadas.", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1003", "titulo": "Formato 1003", "descripcion": "Retenciones en la fuente que te practicaron.", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1005", "titulo": "Formato 1005", "descripcion": "Impuesto a las ventas por pagar (descontable).", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1006", "titulo": "Formato 1006", "descripcion": "Impuesto a las ventas por pagar (generado) e impuesto al consumo.", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1007", "titulo": "Formato 1007", "descripcion": "Ingresos recibidos en el año.", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1008", "titulo": "Formato 1008", "descripcion": "Saldo de cuentas por cobrar.", "estado": "activo", "exporta": "Excel"},
            {"slug": "formato-1009", "titulo": "Formato 1009", "descripcion": "Saldo de cuentas por pagar.", "estado": "activo", "exporta": "Excel"},
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
    cursor = db.facturas.find({"empresa_id": empresa_id, **NO_ANULADO, "fecha": {"$gte": desde, "$lte": hasta}})
    return [d async for d in cursor]


async def _pos(empresa_id: str, desde: str, hasta: str):
    db = get_db()
    cursor = db.documentos_pos.find({"empresa_id": empresa_id, **NO_ANULADO, "fecha": {"$gte": desde, "$lte": hasta}})
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
        async for p in db.productos.find({"empresa_id": empresa_id})
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
    filas = [{"fecha": k, **{kk: redondear(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
             for k, v in sorted(por_dia.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documentos", "label": "Documentos"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas,
        {"documentos": len(docs),
         "subtotal": redondear(sum(d.get("subtotal", 0) for d in docs), 2),
         "iva": redondear(sum(d.get("iva_total", 0) for d in docs), 2),
         "total": redondear(sum(d.get("total", 0) for d in docs), 2)},
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
                      **{k: redondear(v, 2) for k, v in a.items()}})
    filas.sort(key=lambda f: -f["total"])
    return _tabla(
        [{"key": "sku", "label": "SKU"}, {"key": "item", "label": "Ítem"},
         {"key": "cantidad", "label": "Cantidad"}, {"key": "subtotal", "label": "Subtotal"},
         {"key": "iva", "label": "IVA"}, {"key": "total", "label": "Total"}],
        filas, {"items": len(filas), "total": redondear(sum(f["total"] for f in filas), 2)},
    )


async def r_ventas_por_cliente(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta):
        a = acc[d.get("cliente_nombre") or "Sin cliente"]
        a["documentos"] += 1
        a["subtotal"] += d.get("subtotal", 0)
        a["iva"] += d.get("iva_total", 0)
        a["total"] += d.get("total", 0)
    filas = [{"cliente": k, **{kk: redondear(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
             for k, v in sorted(acc.items(), key=lambda x: -x[1]["total"])]
    return _tabla(
        [{"key": "cliente", "label": "Cliente"}, {"key": "documentos", "label": "Documentos"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas, {"clientes": len(filas), "total": redondear(sum(f["total"] for f in filas), 2)},
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
            "cantidad": redondear(a["cantidad"], 2), "ingreso": redondear(a["ingreso"], 2),
            "costo": redondear(a["costo"], 2), "utilidad": redondear(utilidad, 2),
            "margen": f"{margen:.1f}%",
        })
    filas.sort(key=lambda f: -f["utilidad"])
    return _tabla(
        [{"key": "item", "label": "Ítem"}, {"key": "cantidad", "label": "Cantidad"},
         {"key": "ingreso", "label": "Ingreso"}, {"key": "costo", "label": "Costo"},
         {"key": "utilidad", "label": "Utilidad"}, {"key": "margen", "label": "Margen"}],
        filas, {"utilidad_total": redondear(sum(f["utilidad"] for f in filas), 2)},
    )


async def r_estado_cuenta_por_cliente(empresa_id, desde, hasta):
    terceros = await _mapa_terceros(empresa_id)
    filas = []
    for d in await _facturas(empresa_id, desde, hasta):
        filas.append({
            "fecha": d.get("fecha"),
            "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
            "cliente": d.get("cliente_nombre") or terceros.get(d.get("cliente_id", ""), ""),
            "total": redondear(d.get("total", 0), 2),
            "estado": d.get("estado_dian", "borrador"),
        })
    filas.sort(key=lambda f: (f["cliente"], f["fecha"] or ""))
    return _tabla(
        [{"key": "cliente", "label": "Cliente"}, {"key": "fecha", "label": "Fecha"},
         {"key": "documento", "label": "Documento"}, {"key": "total", "label": "Total"},
         {"key": "estado", "label": "Estado"}],
        filas, {"documentos": len(filas), "total": redondear(sum(f["total"] for f in filas), 2)},
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
              "documentos": v["documentos"], "total": redondear(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "numeracion", "label": "Numeración"},
         {"key": "forma_pago", "label": "Forma de pago"},
         {"key": "documentos", "label": "Documentos"}, {"key": "total", "label": "Total"}],
        filas, {"total": redondear(sum(f["total"] for f in filas), 2)},
    )


async def r_cuentas_por_cobrar(empresa_id, desde, hasta):
    filas = []
    docs = await _facturas(empresa_id, desde, hasta)
    docs += [d async for d in get_db().cartera_inicial.find(
        {"empresa_id": empresa_id, "tipo": "cxc", "fecha": {"$gte": desde, "$lte": hasta}})]
    for d in docs:
        filas.append({
            "documento": d.get("numero_documento") or f"{d.get('prefijo','')}{d.get('consecutivo','')}",
            "cliente": d.get("cliente_nombre", ""),
            "fecha": d.get("fecha"),
            "vencimiento": d.get("fecha_vencimiento", "—"),
            "total": redondear(d.get("total", 0), 2),
            "saldo": redondear(d.get("saldo_pendiente", d.get("total", 0)), 2),
        })
    return _tabla(
        [{"key": "documento", "label": "Documento"}, {"key": "cliente", "label": "Cliente"},
         {"key": "fecha", "label": "Fecha"}, {"key": "vencimiento", "label": "Vencimiento"},
         {"key": "total", "label": "Total"}, {"key": "saldo", "label": "Saldo"}],
        filas, {"cartera": redondear(sum(f["saldo"] for f in filas), 2)},
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
        filas.append({"codigo": codigo, "cuenta": nombre, "tipo": tipo, "valor": redondear(valor, 2)})
    return _tabla(
        [{"key": "codigo", "label": "Código"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "tipo", "label": "Tipo"}, {"key": "valor", "label": "Valor"}],
        filas, {"ingresos": redondear(ingresos, 2), "gastos": redondear(gastos, 2),
                "resultado": redondear(ingresos - gastos, 2)},
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
            "cantidad": redondear(cant, 2), "costo_promedio": redondear(costo, 2),
            "valor": redondear(cant * costo, 2),
        })
    return _tabla(
        [{"key": "sku", "label": "SKU"}, {"key": "producto", "label": "Producto"},
         {"key": "bodega", "label": "Bodega"}, {"key": "cantidad", "label": "Cantidad"},
         {"key": "costo_promedio", "label": "Costo prom."}, {"key": "valor", "label": "Valor"}],
        filas, {"valor_total": redondear(sum(f["valor"] for f in filas), 2)},
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
        "debito": redondear(a.get("debito", 0), 2),
        "credito": redondear(a.get("credito", 0), 2),
    } for a in await _asientos(empresa_id, desde, hasta)]
    filas.sort(key=lambda f: (f["fecha"] or "", f["cuenta"]))
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "nombre_cuenta", "label": "Nombre"}, {"key": "tercero", "label": "Tercero"},
         {"key": "referencia", "label": "Referencia"}, {"key": "debito", "label": "Débito"},
         {"key": "credito", "label": "Crédito"}],
        filas, {"debitos": redondear(sum(f["debito"] for f in filas), 2),
                "creditos": redondear(sum(f["credito"] for f in filas), 2)},
    )


async def r_reporte_anual(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "total": 0.0})
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        mes = (d.get("fecha") or "")[:7]
        acc[mes]["documentos"] += 1
        acc[mes]["total"] += d.get("total", 0)
    filas = [{"periodo": k, "documentos": v["documentos"], "total": redondear(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "periodo", "label": "Periodo"}, {"key": "documentos", "label": "Documentos"},
         {"key": "total", "label": "Total"}],
        filas, {"total": redondear(sum(f["total"] for f in filas), 2)},
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
    filas = [{"codigo": c, "cuenta": n, "debito": redondear(v["debito"], 2),
              "credito": redondear(v["credito"], 2),
              "saldo": redondear(v["debito"] - v["credito"], 2)}
             for (c, n), v in sorted(acc.items())]
    return _tabla(
        [{"key": "codigo", "label": "Código"}, {"key": "cuenta", "label": "Cuenta"},
         {"key": "debito", "label": "Débito"}, {"key": "credito", "label": "Crédito"},
         {"key": "saldo", "label": "Saldo"}],
        filas, {"debitos": redondear(sum(f["debito"] for f in filas), 2),
                "creditos": redondear(sum(f["credito"] for f in filas), 2)},
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
    filas = [{"tercero": t, "codigo": c, "cuenta": n, "debito": redondear(v["debito"], 2),
              "credito": redondear(v["credito"], 2), "saldo": redondear(v["debito"] - v["credito"], 2)}
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
        filas.append({"grupo": grupo, "codigo": codigo, "cuenta": nombre, "valor": redondear(valor, 2)})
    return _tabla(
        [{"key": "grupo", "label": "Grupo"}, {"key": "codigo", "label": "Código"},
         {"key": "cuenta", "label": "Cuenta"}, {"key": "valor", "label": "Valor"}],
        filas, {"ingresos": redondear(ingresos, 2), "costos": redondear(costos, 2),
                "gastos": redondear(gastos, 2),
                "utilidad": redondear(ingresos - costos - gastos, 2)},
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
        filas.append({"grupo": grupo, "codigo": codigo, "cuenta": nombre, "valor": redondear(valor, 2)})
    return _tabla(
        [{"key": "grupo", "label": "Grupo"}, {"key": "codigo", "label": "Código"},
         {"key": "cuenta", "label": "Cuenta"}, {"key": "valor", "label": "Valor"}],
        filas, {"activo": redondear(activo, 2), "pasivo": redondear(pasivo, 2),
                "patrimonio": redondear(patrimonio, 2)},
    )


async def r_form_300_iva(empresa_id, desde, hasta):
    """Liquidación del IVA del periodo: ventas por tarifa (netas de notas), IVA descontable y saldo."""
    db = get_db()
    docs = await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta)
    notas = [n async for n in db.notas_credito_debito.find(
        {"empresa_id": empresa_id, **NO_ANULADO, "fecha": {"$gte": desde, "$lte": hasta}})]
    ventas = defaultdict(lambda: {"base": 0.0, "iva": 0.0})   # tarifa -> valores netos
    for d in docs:
        for it in d.get("items", []):
            t = float(it.get("tarifa_iva", 0) or 0)
            ventas[t]["base"] += it.get("subtotal", 0)
            ventas[t]["iva"] += it.get("iva", 0)
    for n in notas:
        signo = -1 if n.get("tipo") == "credito" else 1
        for it in n.get("items", []):
            t = float(it.get("tarifa_iva", 0) or 0)
            ventas[t]["base"] += signo * it.get("subtotal", 0)
            ventas[t]["iva"] += signo * it.get("iva", 0)

    filas, gravadas, iva_generado, base_cero = [], 0.0, 0.0, 0.0
    for t in sorted(ventas):
        v = ventas[t]
        if t > 0:
            filas.append({"seccion": "Ingresos", "concepto": f"Ventas gravadas a la tarifa del {t:g}% (netas de notas)",
                          "base": redondear(v["base"], 2), "impuesto": redondear(v["iva"], 2)})
            gravadas += v["base"]
            iva_generado += v["iva"]
        else:
            base_cero += v["base"]
    filas.append({"seccion": "Ingresos", "concepto": "Ventas a tarifa 0% (excluidas, exentas o no gravadas, netas de notas)",
                  "base": redondear(base_cero, 2), "impuesto": 0})

    compras_base = compras_iva = reteiva_practicada = 0.0
    for f in await _facturas_proveedor(empresa_id, desde, hasta):
        compras_base += f.get("subtotal", 0)
        compras_iva += f.get("iva_total", 0)
        reteiva_practicada += (f.get("retenciones") or {}).get("reteiva", 0)
    filas.append({"seccion": "Compras", "concepto": "Compras con IVA descontable", "base": redondear(compras_base, 2),
                  "impuesto": redondear(compras_iva, 2)})

    reteiva_sufrida = sum((d.get("retenciones") or {}).get("reteiva", 0) for d in docs)
    for n in notas:
        signo = -1 if n.get("tipo") == "credito" else 1
        reteiva_sufrida += signo * (n.get("retenciones") or {}).get("reteiva", 0)

    saldo = iva_generado - compras_iva
    filas.append({"seccion": "Liquidación", "concepto": "IVA generado", "base": None, "impuesto": redondear(iva_generado, 2)})
    filas.append({"seccion": "Liquidación", "concepto": "(-) IVA descontable", "base": None, "impuesto": redondear(compras_iva, 2)})
    filas.append({"seccion": "Liquidación", "concepto": "(-) ReteIVA que te practicaron", "base": None, "impuesto": redondear(reteiva_sufrida, 2)})
    neto = saldo - reteiva_sufrida
    filas.append({"seccion": "Liquidación", "concepto": "Saldo a pagar" if neto >= 0 else "Saldo a favor",
                  "base": None, "impuesto": redondear(abs(neto), 2)})
    return _tabla(
        [{"key": "seccion", "label": "Sección"}, {"key": "concepto", "label": "Concepto"},
         {"key": "base", "label": "Base"}, {"key": "impuesto", "label": "Impuesto"}],
        filas,
        {"ventas_gravadas": redondear(gravadas, 2), "iva_generado": redondear(iva_generado, 2),
         "iva_descontable": redondear(compras_iva, 2), "reteiva_sufrida": redondear(reteiva_sufrida, 2),
         "reteiva_practicada_por_pagar": redondear(reteiva_practicada, 2),
         "saldo_a_pagar": redondear(max(neto, 0), 2), "saldo_a_favor": redondear(max(-neto, 0), 2)},
    )


async def _ingresos_simple(empresa_id, desde, hasta) -> float:
    """Ingresos brutos del periodo según el libro (clase 4, netos de devoluciones y descuentos)."""
    acc = await _saldos_por_cuenta(empresa_id, desde, hasta)
    return sum(v["credito"] - v["debito"] for (codigo, _), v in acc.items() if codigo.startswith("4"))


async def _pension_empleador(empresa_id, desde, hasta) -> float:
    """Aportes a pensión a cargo del empleador liquidados en nómina (descuento del art. 903 ET)."""
    total = 0.0
    async for per in get_db().nomina_periodos.find(
        {"empresa_id": empresa_id, **NO_ANULADO, "fecha_fin": {"$gte": desde, "$lte": hasta}}
    ):
        total += sum(float((l.get("aportes_empleador") or {}).get("pension", 0)) for l in per.get("lineas", []))
    return total


async def _contexto_simple(empresa_id):
    empresa = await get_db().empresas.find_one({"_id": ObjectId(empresa_id)}) or {}
    tarifas = await simple.obtener(empresa_id)
    grupo = str(empresa.get("grupo_simple") or 2)
    return empresa, tarifas, tarifas["grupos"][grupo], grupo


def _aviso_simple(empresa, tarifas, grupo):
    avisos = []
    if empresa.get("regimen_tributario") != "SIMPLE":
        avisos.append("La empresa no está en el régimen SIMPLE: este formulario es solo informativo.")
    if not tarifas["verificado"]:
        avisos.append("Las tarifas no están marcadas como verificadas: confírmalas con tu contador (Configuración › Tarifas SIMPLE).")
    return " ".join(avisos) or None


async def r_form_2593_simple(empresa_id, desde, hasta):
    """Recibo electrónico SIMPLE: anticipo bimestral = ingresos del bimestre × tarifa del tramo acumulado del año."""
    anio, mes = int(hasta[:4]), int(hasta[5:7])
    bim = (mes - 1) // 2
    ini_bim, fin_bim = f"{anio}-{bim * 2 + 1:02d}-01", hasta
    empresa, tarifas, grupo, nombre_grupo = await _contexto_simple(empresa_id)
    uvt = valor_uvt(anio)
    ingresos_bim = await _ingresos_simple(empresa_id, ini_bim, fin_bim)
    acumulado = await _ingresos_simple(empresa_id, f"{anio}-01-01", fin_bim)
    tarifa, en_uvt = simple.tarifa_para(grupo, acumulado, uvt)
    anticipo = ingresos_bim * tarifa / 100
    pension = await _pension_empleador(empresa_id, ini_bim, fin_bim)
    a_pagar = max(anticipo - pension, 0)
    filas = [
        {"concepto": f"Bimestre {bim + 1} de {anio}", "valor": None},
        {"concepto": "Grupo de actividad", "valor": f"{nombre_grupo} — {grupo['nombre']}"},
        {"concepto": "Ingresos brutos del bimestre", "valor": redondear(ingresos_bim, 2)},
        {"concepto": f"Ingresos brutos acumulados del año ({en_uvt:,.0f} UVT)", "valor": redondear(acumulado, 2)},
        {"concepto": "Tarifa SIMPLE consolidada aplicable (%)", "valor": tarifa},
        {"concepto": "Anticipo bimestral", "valor": redondear(anticipo, 2)},
        {"concepto": "(-) Descuento por aportes a pensión del empleador", "valor": redondear(pension, 2)},
        {"concepto": "Valor a pagar", "valor": redondear(a_pagar, 2)},
    ]
    return _tabla([{"key": "concepto", "label": "Concepto"}, {"key": "valor", "label": "Valor"}], filas,
                  {"ingresos_bimestre": redondear(ingresos_bim, 2), "tarifa": tarifa, "anticipo": redondear(anticipo, 2),
                   "valor_a_pagar": redondear(a_pagar, 2), "advertencia": _aviso_simple(empresa, tarifas, grupo)})


async def r_form_260_simple(empresa_id, desde, hasta):
    """Declaración anual consolidada SIMPLE: impuesto del año menos anticipos bimestrales y descuento por pensión."""
    anio = int(desde[:4])
    empresa, tarifas, grupo, nombre_grupo = await _contexto_simple(empresa_id)
    uvt = valor_uvt(anio)
    ultimos = {1: "02-28", 2: "04-30", 3: "06-30", 4: "08-31", 5: "10-31", 6: "12-31"}
    filas, acumulado, anticipos = [], 0.0, 0.0
    for b in range(1, 7):
        ini, fin = f"{anio}-{b * 2 - 1:02d}-01", f"{anio}-{ultimos[b]}"
        ing = await _ingresos_simple(empresa_id, ini, fin)
        acumulado += ing
        tarifa, _ = simple.tarifa_para(grupo, acumulado, uvt)
        ant = ing * tarifa / 100
        anticipos += ant
        filas.append({"periodo": f"Bimestre {b}", "ingresos": redondear(ing, 2), "acumulado": redondear(acumulado, 2),
                      "tarifa": tarifa, "anticipo": redondear(ant, 2)})
    tarifa_anual, en_uvt = simple.tarifa_para(grupo, acumulado, uvt)
    impuesto = acumulado * tarifa_anual / 100
    pension = await _pension_empleador(empresa_id, f"{anio}-01-01", f"{anio}-12-31")
    saldo = impuesto - pension - anticipos
    return _tabla(
        [{"key": "periodo", "label": "Periodo"}, {"key": "ingresos", "label": "Ingresos del bimestre"},
         {"key": "acumulado", "label": "Acumulado"}, {"key": "tarifa", "label": "Tarifa %"},
         {"key": "anticipo", "label": "Anticipo bimestral"}],
        filas,
        {"anio": anio, "grupo": f"{nombre_grupo} — {grupo['nombre']}", "ingresos_brutos_anuales": redondear(acumulado, 2),
         "ingresos_en_uvt": redondear(en_uvt, 0), "tarifa_anual": tarifa_anual, "impuesto_consolidado": redondear(impuesto, 2),
         "descuento_pension_empleador": redondear(pension, 2), "anticipos_bimestrales": redondear(anticipos, 2),
         "saldo_a_pagar": redondear(max(saldo, 0), 2), "saldo_a_favor": redondear(max(-saldo, 0), 2),
         "advertencia": _aviso_simple(empresa, tarifas, grupo)},
    )


async def r_reporte_detallado_impuestos(empresa_id, desde, hasta):
    filas = []
    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        for it in d.get("items", []):
            filas.append({
                "fecha": d.get("fecha"),
                "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
                "impuesto": f"IVA {it.get('tarifa_iva', 0)}%",
                "base": redondear(it.get("subtotal", 0), 2),
                "valor": redondear(it.get("iva", 0), 2),
            })
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "impuesto", "label": "Impuesto"}, {"key": "base", "label": "Base"},
         {"key": "valor", "label": "Valor"}],
        filas, {"total_impuestos": redondear(sum(f["valor"] for f in filas), 2)},
    )


async def r_impuestos_y_retenciones(empresa_id, desde, hasta):
    """IVA, impuesto al consumo, retenciones practicadas y sufridas, y autorretenciones, documento a documento."""
    filas: list[dict] = []
    resumen = defaultdict(float)

    def agregar(fecha, documento, impuesto, base, valor, clave):
        if not valor:
            return
        filas.append({"fecha": fecha or "", "documento": documento or "", "impuesto": impuesto,
                      "base": redondear(base, 2), "valor": redondear(valor, 2)})
        resumen[clave] += valor

    for d in await _facturas(empresa_id, desde, hasta) + await _pos(empresa_id, desde, hasta):
        num = d.get("numero", "")
        agregar(d.get("fecha"), num, "IVA generado", d.get("subtotal", 0), d.get("iva_total", 0), "iva_generado")
        agregar(d.get("fecha"), num, "Impuesto al consumo", d.get("subtotal", 0), d.get("inc_total", 0), "impuesto_consumo")
        ret = d.get("retenciones") or {}
        for clave, etiqueta in (("retefuente", "ReteFuente que te practicaron"),
                                ("reteiva", "ReteIVA que te practicaron"),
                                ("reteica", "ReteICA que te practicaron")):
            agregar(d.get("fecha"), num, etiqueta, d.get("subtotal", 0), ret.get(clave, 0), "retenciones_que_te_practicaron")
        agregar(d.get("fecha"), num, "Autorretención de renta", d.get("subtotal", 0), d.get("autorretencion", 0), "autorretenciones")

    for f in await _facturas_proveedor(empresa_id, desde, hasta):
        doc = f"{f.get('numero', '')} · {f.get('numero_factura', '')}"
        agregar(f.get("fecha"), doc, "IVA descontable", f.get("subtotal", 0), f.get("iva_total", 0), "iva_descontable")
        ret = f.get("retenciones") or {}
        for clave, etiqueta in (("retefuente", "ReteFuente practicada"), ("reteiva", "ReteIVA practicada"),
                                ("reteica", "ReteICA practicada")):
            base = f.get("iva_total", 0) if clave == "reteiva" else f.get("subtotal", 0)
            agregar(f.get("fecha"), doc, etiqueta, base, ret.get(clave, 0), "retenciones_practicadas")

    filas.sort(key=lambda x: x["fecha"])
    resumen = {k: redondear(v, 2) for k, v in resumen.items()}
    resumen["iva_a_pagar"] = redondear(resumen.get("iva_generado", 0) - resumen.get("iva_descontable", 0), 2)
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "impuesto", "label": "Impuesto o retención"}, {"key": "base", "label": "Base"},
         {"key": "valor", "label": "Valor"}],
        filas, dict(resumen),
    )


async def r_comprobante_informe_diario(empresa_id, desde, hasta):
    acc = defaultdict(lambda: {"documentos": 0, "subtotal": 0.0, "iva": 0.0, "total": 0.0})
    for d in await _pos(empresa_id, desde, hasta):
        a = acc[d.get("fecha", "")]
        a["documentos"] += 1
        a["subtotal"] += d.get("subtotal", 0)
        a["iva"] += d.get("iva_total", 0)
        a["total"] += d.get("total", 0)
    filas = [{"fecha": k, "documentos": v["documentos"], "subtotal": redondear(v["subtotal"], 2),
              "iva": redondear(v["iva"], 2), "total": redondear(v["total"], 2)}
             for k, v in sorted(acc.items())]
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documentos", "label": "Documentos POS"},
         {"key": "subtotal", "label": "Subtotal"}, {"key": "iva", "label": "IVA"},
         {"key": "total", "label": "Total"}],
        filas, {"total": redondear(sum(f["total"] for f in filas), 2)},
    )


async def r_exportar_facturas(empresa_id, desde, hasta):
    filas = [{
        "documento": f"{d.get('prefijo','')}{d.get('consecutivo','')}",
        "fecha": d.get("fecha"), "cliente": d.get("cliente_nombre", ""),
        "subtotal": redondear(d.get("subtotal", 0), 2), "iva": redondear(d.get("iva_total", 0), 2),
        "total": redondear(d.get("total", 0), 2), "estado_dian": d.get("estado_dian", ""),
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
        {"empresa_id": empresa_id, **NO_ANULADO, "fecha": {"$gte": desde, "$lte": hasta}})]


async def r_cuentas_por_pagar(empresa_id, desde, hasta):
    db = get_db()
    filas = []
    async for f in cartera.iterar(db, empresa_id, "cxp"):
        saldo = float(f.get("saldo_pendiente", f.get("total_a_pagar", 0)))
        if saldo <= 0.009:
            continue
        filas.append({
            "fecha": f.get("fecha"), "documento": f.get("numero_factura", ""),
            "proveedor": f.get("proveedor_nombre", ""),
            "vencimiento": f.get("fecha_vencimiento") or "",
            "total": f.get("total_a_pagar", 0), "saldo": redondear(saldo, 2),
        })
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "documento", "label": "Documento"},
         {"key": "proveedor", "label": "Proveedor"}, {"key": "vencimiento", "label": "Vencimiento"},
         {"key": "total", "label": "Total"}, {"key": "saldo", "label": "Saldo"}],
        filas, {"saldo_total": redondear(sum(f["saldo"] for f in filas), 2),
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
        filas, {"subtotal": redondear(sum(f["subtotal"] for f in filas), 2),
                "iva": redondear(sum(f["iva"] for f in filas), 2),
                "total": redondear(sum(f["total"] for f in filas), 2),
                "documentos": len(filas)},
    )


async def r_flujo_de_caja(empresa_id, desde, hasta):
    db = get_db()
    por_dia = defaultdict(lambda: {"ingresos": 0.0, "egresos": 0.0})
    async for m in db.movimientos_tesoreria.find(
        {"empresa_id": empresa_id, **NO_ANULADO, "fecha": {"$gte": desde, "$lte": hasta}}
    ):
        clave = "ingresos" if m.get("tipo") == "ingreso" else "egresos"
        por_dia[m.get("fecha")][clave] += float(m.get("valor", 0))
    filas, acumulado = [], 0.0
    for fecha in sorted(k for k in por_dia if k):
        ing = redondear(por_dia[fecha]["ingresos"], 2)
        egr = redondear(por_dia[fecha]["egresos"], 2)
        acumulado += ing - egr
        filas.append({"fecha": fecha, "ingresos": ing, "egresos": egr,
                      "neto": redondear(ing - egr, 2), "acumulado": redondear(acumulado, 2)})
    return _tabla(
        [{"key": "fecha", "label": "Fecha"}, {"key": "ingresos", "label": "Ingresos"},
         {"key": "egresos", "label": "Egresos"}, {"key": "neto", "label": "Neto"},
         {"key": "acumulado", "label": "Acumulado"}],
        filas, {"ingresos": redondear(sum(f["ingresos"] for f in filas), 2),
                "egresos": redondear(sum(f["egresos"] for f in filas), 2),
                "neto": redondear(acumulado, 2)},
    )


async def r_formulario_350(empresa_id, desde, hasta):
    """Retenciones en la fuente practicadas (base para el formulario 350)."""
    facturas = await _facturas_proveedor(empresa_id, desde, hasta)
    base = redondear(sum(f.get("subtotal", 0) for f in facturas), 2)
    rte = redondear(sum(f.get("retenciones", {}).get("retefuente", 0) for f in facturas), 2)
    ica = redondear(sum(f.get("retenciones", {}).get("reteica", 0) for f in facturas), 2)
    iva = redondear(sum(f.get("retenciones", {}).get("reteiva", 0) for f in facturas), 2)
    # Autorretención de renta: se declara junto con las retenciones practicadas.
    ventas = await _facturas(empresa_id, desde, hasta)
    autorret = redondear(sum(v.get("autorretencion", 0) for v in ventas), 2)
    base_autorret = redondear(sum(v.get("subtotal", 0) for v in ventas if v.get("autorretencion")), 2)
    laboral = await _retencion_laboral(empresa_id, desde, hasta)
    total = redondear(rte + iva + ica + autorret + laboral, 2)
    filas = [
        {"concepto": "Base sujeta a retención (compras)", "valor": base},
        {"concepto": "Retención en la fuente a título de renta (compras y servicios)", "valor": rte},
        {"concepto": "Retención en la fuente por pagos laborales", "valor": laboral},
        {"concepto": "Base de autorretención de renta (ventas)", "valor": base_autorret},
        {"concepto": "Autorretención de renta", "valor": autorret},
        {"concepto": "Retención de IVA (reteIVA)", "valor": iva},
        {"concepto": "Retención de ICA (reteICA, se declara en el municipio)", "valor": ica},
        {"concepto": "Total retenciones y autorretenciones a declarar (sin ICA)", "valor": redondear(total - ica, 2)},
    ]
    return _tabla(
        [{"key": "concepto", "label": "Concepto"}, {"key": "valor", "label": "Valor"}],
        filas, {"base": base, "retefuente": rte, "laboral": laboral, "autorretencion": autorret,
                "reteiva": iva, "reteica": ica, "total": redondear(total - ica, 2)},
    )


async def _retencion_laboral(empresa_id, desde, hasta) -> float:
    """Retención en la fuente practicada en nómina (liquidaciones del rango, no anuladas)."""
    total = 0.0
    async for p in get_db().nomina_periodos.find(
        {"empresa_id": empresa_id, "fecha_fin": {"$gte": desde, "$lte": hasta}, **NO_ANULADO}
    ):
        total += float(p.get("totales", {}).get("retefuente", 0))
    return redondear(total, 2)


# ---------------------------------------------------------------------------
# Información exógena (Fase 3) — formatos DIAN
# ---------------------------------------------------------------------------

COLS_TERCERO = [
    {"key": "tipo_documento", "label": "Tipo doc."},
    {"key": "numero_documento", "label": "N° documento"},
    {"key": "razon_social", "label": "Razón social / Nombre"},
]


async def _terceros_detalle(empresa_id: str):
    db = get_db()
    return {str(t["_id"]): t async for t in db.terceros.find({"empresa_id": empresa_id})}


def _datos_tercero(t: dict | None, nombre_fallback: str = "") -> dict:
    t = t or {}
    return {
        "tipo_documento": t.get("tipo_documento", "31"),
        "numero_documento": t.get("numero_documento") or t.get("nit", ""),
        "razon_social": t.get("nombre") or nombre_fallback or "Sin identificar",
    }


async def _exogena_compras(empresa_id, desde, hasta):
    return await _facturas_proveedor(empresa_id, desde, hasta)


async def r_formato_1001(empresa_id, desde, hasta):
    """Pagos o abonos en cuenta y retenciones practicadas."""
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(lambda: {"pago": 0.0, "retefuente": 0.0, "reteiva": 0.0, "reteica": 0.0})
    nombres = {}
    for f in await _exogena_compras(empresa_id, desde, hasta):
        k = f.get("proveedor_id") or f.get("proveedor_nombre", "—")
        nombres[k] = f.get("proveedor_nombre", "")
        ret = f.get("retenciones", {}) or {}
        a = acc[k]
        a["pago"] += float(f.get("subtotal", 0))
        a["retefuente"] += float(ret.get("retefuente", 0))
        a["reteiva"] += float(ret.get("reteiva", 0))
        a["reteica"] += float(ret.get("reteica", 0))
    filas = [
        {**_datos_tercero(terceros.get(k), nombres.get(k, "")),
         **{kk: redondear(vv, 2) for kk, vv in v.items()}}
        for k, v in acc.items()
    ]
    filas.sort(key=lambda f: -f["pago"])
    return _tabla(
        COLS_TERCERO + [
            {"key": "pago", "label": "Pago o abono en cuenta"},
            {"key": "retefuente", "label": "Retención practicada renta"},
            {"key": "reteiva", "label": "ReteIVA practicada"},
            {"key": "reteica", "label": "ReteICA practicada"},
        ],
        filas,
        {"terceros": len(filas),
         "pagos": redondear(sum(f["pago"] for f in filas), 2),
         "retenciones": redondear(sum(f["retefuente"] + f["reteiva"] + f["reteica"] for f in filas), 2)},
    )


async def r_formato_1003(empresa_id, desde, hasta):
    """Retenciones en la fuente que le practicaron (informadas en ventas)."""
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(lambda: {"base": 0.0, "retencion": 0.0})
    nombres = {}
    for f in await _facturas(empresa_id, desde, hasta):
        ret = f.get("retenciones", {}) or {}
        total_ret = sum(float(v) for v in ret.values() if isinstance(v, (int, float)))
        if total_ret <= 0:
            continue
        k = f.get("cliente_id") or f.get("cliente_nombre", "—")
        nombres[k] = f.get("cliente_nombre", "")
        acc[k]["base"] += float(f.get("subtotal", 0))
        acc[k]["retencion"] += total_ret
    filas = [
        {**_datos_tercero(terceros.get(k), nombres.get(k, "")),
         "base": redondear(v["base"], 2), "retencion": redondear(v["retencion"], 2)}
        for k, v in acc.items()
    ]
    return _tabla(
        COLS_TERCERO + [{"key": "base", "label": "Base sometida"},
                        {"key": "retencion", "label": "Retención que le practicaron"}],
        filas, {"terceros": len(filas),
                "retencion": redondear(sum(f["retencion"] for f in filas), 2)},
    )


async def r_formato_1005(empresa_id, desde, hasta):
    """IVA descontable (compras)."""
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(lambda: {"base": 0.0, "iva": 0.0})
    nombres = {}
    for f in await _exogena_compras(empresa_id, desde, hasta):
        if float(f.get("iva_total", 0)) <= 0:
            continue
        k = f.get("proveedor_id") or f.get("proveedor_nombre", "—")
        nombres[k] = f.get("proveedor_nombre", "")
        acc[k]["base"] += float(f.get("subtotal", 0))
        acc[k]["iva"] += float(f.get("iva_total", 0))
    filas = [{**_datos_tercero(terceros.get(k), nombres.get(k, "")),
              "base": redondear(v["base"], 2), "iva": redondear(v["iva"], 2)} for k, v in acc.items()]
    return _tabla(
        COLS_TERCERO + [{"key": "base", "label": "Base"},
                        {"key": "iva", "label": "IVA descontable"}],
        filas, {"terceros": len(filas), "iva": redondear(sum(f["iva"] for f in filas), 2)},
    )


async def r_formato_1006(empresa_id, desde, hasta):
    """IVA generado (ventas)."""
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(lambda: {"base": 0.0, "iva": 0.0})
    nombres = {}
    for f in await _facturas(empresa_id, desde, hasta):
        if float(f.get("iva_total", 0)) <= 0:
            continue
        k = f.get("cliente_id") or f.get("cliente_nombre", "—")
        nombres[k] = f.get("cliente_nombre", "")
        acc[k]["base"] += float(f.get("subtotal", 0))
        acc[k]["iva"] += float(f.get("iva_total", 0))
    filas = [{**_datos_tercero(terceros.get(k), nombres.get(k, "")),
              "base": redondear(v["base"], 2), "iva": redondear(v["iva"], 2)} for k, v in acc.items()]
    return _tabla(
        COLS_TERCERO + [{"key": "base", "label": "Base"},
                        {"key": "iva", "label": "IVA generado"}],
        filas, {"terceros": len(filas), "iva": redondear(sum(f["iva"] for f in filas), 2)},
    )


async def r_formato_1007(empresa_id, desde, hasta):
    """Ingresos recibidos en el periodo, por tercero."""
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(float)
    nombres = {}
    for f in await _facturas(empresa_id, desde, hasta):
        k = f.get("cliente_id") or f.get("cliente_nombre", "—")
        nombres[k] = f.get("cliente_nombre", "")
        acc[k] += float(f.get("subtotal", 0))
    pos_total = redondear(sum(float(d.get("subtotal", 0)) for d in await _pos(empresa_id, desde, hasta)), 2)
    filas = [{**_datos_tercero(terceros.get(k), nombres.get(k, "")), "ingreso": redondear(v, 2)}
             for k, v in sorted(acc.items(), key=lambda x: -x[1])]
    if pos_total:
        filas.append({"tipo_documento": "43", "numero_documento": "222222222",
                      "razon_social": "Cuantías menores (POS)", "ingreso": pos_total})
    return _tabla(
        COLS_TERCERO + [{"key": "ingreso", "label": "Ingreso bruto recibido"}],
        filas, {"terceros": len(filas), "ingresos": redondear(sum(f["ingreso"] for f in filas), 2)},
    )


async def r_formato_1008(empresa_id, desde, hasta):
    """Saldo de cuentas por cobrar al corte."""
    db = get_db()
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(float)
    nombres = {}
    async for f in cartera.iterar(db, empresa_id, "cxc", {"fecha": {"$lte": hasta}}):
        saldo = float(f.get("saldo_pendiente", f.get("total", 0)))
        if saldo <= 0.009:
            continue
        k = f.get("cliente_id") or f.get("cliente_nombre", "—")
        nombres[k] = f.get("cliente_nombre", "")
        acc[k] += saldo
    filas = [{**_datos_tercero(terceros.get(k), nombres.get(k, "")), "saldo": redondear(v, 2)}
             for k, v in sorted(acc.items(), key=lambda x: -x[1])]
    return _tabla(
        COLS_TERCERO + [{"key": "saldo", "label": "Saldo cuentas por cobrar"}],
        filas, {"terceros": len(filas), "saldo": redondear(sum(f["saldo"] for f in filas), 2)},
    )


async def r_formato_1009(empresa_id, desde, hasta):
    """Saldo de cuentas por pagar al corte."""
    db = get_db()
    terceros = await _terceros_detalle(empresa_id)
    acc = defaultdict(float)
    nombres = {}
    async for f in cartera.iterar(db, empresa_id, "cxp", {"fecha": {"$lte": hasta}}):
        saldo = float(f.get("saldo_pendiente", f.get("total_a_pagar", 0)))
        if saldo <= 0.009:
            continue
        k = f.get("proveedor_id") or f.get("proveedor_nombre", "—")
        nombres[k] = f.get("proveedor_nombre", "")
        acc[k] += saldo
    filas = [{**_datos_tercero(terceros.get(k), nombres.get(k, "")), "saldo": redondear(v, 2)}
             for k, v in sorted(acc.items(), key=lambda x: -x[1])]
    return _tabla(
        COLS_TERCERO + [{"key": "saldo", "label": "Saldo cuentas por pagar"}],
        filas, {"terceros": len(filas), "saldo": redondear(sum(f["saldo"] for f in filas), 2)},
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
    ("fiscales", "form-2593-simple"): r_form_2593_simple,
    ("administrativos", "cuentas-por-pagar"): r_cuentas_por_pagar,
    ("administrativos", "compras"): r_compras,
    ("financieros", "flujo-de-caja"): r_flujo_de_caja,
    ("fiscales", "formulario-350"): r_formulario_350,
    ("para-trabajar", "exportar-facturas"): r_exportar_facturas,
    ("para-trabajar", "informe-contador"): r_informe_contador,
    ("exogena", "formato-1001"): r_formato_1001,
    ("exogena", "formato-1003"): r_formato_1003,
    ("exogena", "formato-1005"): r_formato_1005,
    ("exogena", "formato-1006"): r_formato_1006,
    ("exogena", "formato-1007"): r_formato_1007,
    ("exogena", "formato-1008"): r_formato_1008,
    ("exogena", "formato-1009"): r_formato_1009,
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
# Calendario tributario — FASE 3
# ---------------------------------------------------------------------------

@router.get("/calendario-tributario")
async def calendario_tributario(
    anio: int = Query(default=None),
    empresa_id: str = Depends(get_empresa_activa),
    _=Depends(require_permiso("reportes", "leer")),
):
    """Fechas límite de obligaciones fiscales según NIT y régimen de la empresa."""
    from core.calendario import calendario_empresa, resumen_calendario

    db = get_db()
    try:
        filtro = {"_id": ObjectId(empresa_id)}
    except Exception:
        filtro = {"_id": empresa_id}
    empresa = await db.empresas.find_one(filtro) or {}
    nit = str(empresa.get("nit", "") or "")
    regimen = empresa.get("regimen_tributario", "ORDINARIO")
    anio = anio or date.today().year

    obligaciones = calendario_empresa(nit, regimen, anio)
    resumen = resumen_calendario(obligaciones)
    return {
        "titulo": "Calendario tributario",
        "empresa": {"nit": nit, "razon_social": empresa.get("razon_social", ""), "regimen": regimen},
        "anio": anio,
        "nota": "Fechas referenciales calculadas con los patrones históricos DIAN; verificar contra el decreto anual del calendario tributario.",
        "obligaciones": obligaciones,
        "proxima_fecha": resumen["proxima_fecha"],
        "columnas": [
            {"key": "obligacion", "label": "Obligación"},
            {"key": "periodo", "label": "Periodo"},
            {"key": "fecha_limite", "label": "Fecha límite"},
            {"key": "estado", "label": "Estado"},
            {"key": "dias", "label": "Días"},
        ],
        "filas": resumen["planas"],
        "resumen": {
            "total": resumen["total"],
            "vencidas": resumen["vencidas"],
            "proximas_30_dias": resumen["proximas_30_dias"],
        },
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
