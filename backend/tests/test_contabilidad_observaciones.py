"""Aprobación de comprobantes, estado de periodos, consulta unificada, cierre sugerido, auditoría y cartera inicial."""
from tests.test_archivos_usuarios import XLSX, _con_usuario, _importar
from tests.test_documentos import FECHA, _balance, _empresa, _preparar_ventas

RANGO = {"desde": "2026-01-01", "hasta": "2026-12-31"}


def _comp(cuentas, valor=1000, estado="contabilizado", tipo="ajuste", fecha=FECHA, **extra):
    return {"tipo": tipo, "fecha": fecha, "estado": estado, "descripcion": "Prueba",
            "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": valor, **extra},
                       {"cuenta_puc_id": cuentas["3105"], "credito": valor}]}


async def test_auxiliar_requiere_aprobacion_y_el_aprobador_la_otorga(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    u, aux = await _con_usuario(c, nuevo_cliente, "aux@a.co", "auxiliar")

    r = await aux.post("/api/contabilidad/comprobantes", json=_comp(cuentas))
    assert r.status_code == 201, r.text
    comp = r.json()
    assert comp["estado"] == "por_aprobar" and comp["creado_por"] == u["id"]
    assert (await _balance(c)).get("1105", 0) == 0                # aún no llegó al libro

    # El auxiliar no puede aprobar; el administrador sí, y queda quién aprobó.
    assert (await aux.post(f"/api/contabilidad/comprobantes/{comp['id']}/aprobar")).status_code == 403
    r = await c.post(f"/api/contabilidad/comprobantes/{comp['id']}/aprobar")
    assert r.status_code == 200 and r.json()["estado"] == "contabilizado" and r.json()["aprobado_por"]
    assert (await _balance(c))["1105"] == 1000
    assert (await c.post(f"/api/contabilidad/comprobantes/{comp['id']}/aprobar")).status_code == 409

    # Rechazo: vuelve al auxiliar con el motivo y no toca el libro.
    otro = (await aux.post("/api/contabilidad/comprobantes", json=_comp(cuentas, 500))).json()
    assert (await c.post(f"/api/contabilidad/comprobantes/{otro['id']}/rechazar", json={"motivo": "ab"})).status_code == 422
    r = await c.post(f"/api/contabilidad/comprobantes/{otro['id']}/rechazar", json={"motivo": "Falta el soporte"})
    assert r.json()["estado"] == "rechazado" and r.json()["motivo_rechazo"] == "Falta el soporte"
    assert (await _balance(c))["1105"] == 1000
    # Lo corrige y lo reenvía.
    r = await aux.put(f"/api/contabilidad/comprobantes/{otro['id']}", json=_comp(cuentas, 500))
    assert r.json()["estado"] == "por_aprobar"

    # La auditoría muestra acción y usuario por nombre.
    aud = (await c.get("/api/contabilidad/auditoria", params={"documento_id": otro["id"]})).json()
    assert {a["accion"] for a in aud} == {"creado", "rechazado", "editado"}
    assert all(a["usuario_nombre"] for a in aud) and aud[0]["documento_nombre"] == "Comprobante contable"
    assert (await c.get("/api/contabilidad/auditoria", params={"accion": "rechazado"})).json()[0]["numero"] == otro["numero"]

    # El contador (sin marca de aprobación) contabiliza directo.
    _, cont = await _con_usuario(c, nuevo_cliente, "cont@a.co", "contador")
    assert (await cont.post("/api/contabilidad/comprobantes", json=_comp(cuentas, 200))).json()["estado"] == "contabilizado"
    nombres = (await c.get("/api/contabilidad/usuarios-nombres", params={"ids": u["id"]})).json()
    assert nombres == {u["id"]: "Usuario"}


async def test_tercero_por_linea_y_cierre_de_periodos(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    t1 = (await c.post("/api/configuracion/terceros", json={"nombre": "Uno", "tipo": "cliente", "numero_documento": "11"})).json()
    t2 = (await c.post("/api/configuracion/terceros", json={"nombre": "Dos", "tipo": "cliente", "numero_documento": "22"})).json()
    cuerpo = {"tipo": "ajuste", "fecha": "2026-03-10", "estado": "contabilizado", "tercero_id": t1["id"],
              "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": 100, "tercero_id": t2["id"]},
                         {"cuenta_puc_id": cuentas["1105"], "debito": 50},
                         {"cuenta_puc_id": cuentas["3105"], "credito": 150}]}
    assert (await c.post("/api/contabilidad/comprobantes", json=cuerpo)).status_code == 201
    aux = (await c.get("/api/reportes/contables/auxiliar-por-tercero", params=RANGO)).json() if False else None
    docs = (await c.get("/api/contabilidad/documentos", params=RANGO)).json()
    det = (await c.get(f"/api/contabilidad/documentos/comprobante/{docs[0]['documento_id']}/asientos")).json()
    assert [l["tercero"] for l in det["lineas"]] == ["Dos", "Uno", "Uno"]       # la línea con tercero propio lo conserva

    # Estado de los periodos: marzo tiene movimiento; cerramos hasta febrero.
    assert (await c.put("/api/contabilidad/cierre", json={"fecha_cierre": "2026-02-28"})).status_code == 200
    p = (await c.get("/api/contabilidad/cierre/periodos", params={"anio": 2026})).json()
    estados = {m["mes"]: m["estado"] for m in p["meses"]}
    assert estados[1] == "cerrado" and estados[2] == "cerrado" and estados[3] == "abierto"
    assert next(m for m in p["meses"] if m["mes"] == 3)["documentos"] == 1
    assert next(a for a in p["anios"] if a["anio"] == 2026)["estado"] == "parcial"


async def test_consulta_unificada_de_todos_los_modulos(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA, "items": [{"producto_id": prod["id"], "cantidad": 5, "costo_unitario": 10}]})
    await c.post("/api/facturacion/facturas", json={
        "cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
        "items": [{"producto_id": prod["id"], "cantidad": 1, "precio_unitario": 100}]})
    await c.post("/api/contabilidad/comprobantes", json=_comp(cuentas))
    await c.post("/api/contabilidad/comprobantes", json=_comp(cuentas, estado="borrador"))

    docs = (await c.get("/api/contabilidad/documentos", params=RANGO)).json()
    tipos = {d["documento_tipo"] for d in docs}
    assert {"recepcion", "factura", "comprobante"} <= tipos
    assert {d["estado"] for d in docs if d["documento_tipo"] == "comprobante"} == {"contabilizado", "borrador"}
    fact = next(d for d in docs if d["documento_tipo"] == "factura")
    assert fact["tipo_nombre"] == "Factura de venta" and fact["valor"] > 0 and fact["ruta"]
    assert len((await c.get("/api/contabilidad/documentos", params={**RANGO, "tipo": "factura"})).json()) == 1
    assert len((await c.get("/api/contabilidad/documentos", params={**RANGO, "q": fact["numero"]})).json()) == 1
    det = (await c.get(f"/api/contabilidad/documentos/factura/{fact['documento_id']}/asientos")).json()
    assert det["elaboro"] == "Dueño" and det["total_debito"] == det["total_credito"]


async def test_cierre_sugerido_trae_saldos_y_cuadra(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)

    async def mov(deb, cre, valor):
        r = await c.post("/api/contabilidad/comprobantes", json={
            "tipo": "ajuste", "fecha": "2026-05-01", "estado": "contabilizado",
            "lineas": [{"cuenta_puc_id": cuentas[deb], "debito": valor}, {"cuenta_puc_id": cuentas[cre], "credito": valor}]})
        assert r.status_code == 201, r.text

    await mov("1105", "4135", 1000)      # ingreso
    await mov("5195", "1105", 300)       # gasto
    s = (await c.get("/api/contabilidad/cierre-sugerido", params=RANGO)).json()
    assert s["resultado"] == 700 and s["tipo_resultado"] == "utilidad" and s["contrapartida"]["codigo"] == "3605"
    assert {x["codigo"]: x["saldo"] for x in s["saldos"]} == {"4135": 1000, "5195": -300}
    assert sum(l["debito"] for l in s["lineas"]) == sum(l["credito"] for l in s["lineas"]) == 1000

    # Se puede contabilizar tal cual; después las cuentas de resultado quedan en cero.
    cierre = {"tipo": "cierre", "fecha": "2026-12-31", "estado": "contabilizado", "lineas": s["lineas"]}
    assert (await c.post("/api/contabilidad/comprobantes", json=cierre)).status_code == 201
    b = await _balance(c)
    assert b.get("4135", 0) == 0 and b.get("5195", 0) == 0 and b["3605"] == -700
    assert (await c.get("/api/contabilidad/cierre-sugerido", params=RANGO)).json()["lineas"] == []


async def test_saldos_iniciales_de_cartera_quedan_por_documento(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    cli = (await c.post("/api/configuracion/terceros", json={"nombre": "Cliente Uno", "tipo": "cliente", "numero_documento": "1001"})).json()
    pro = (await c.post("/api/configuracion/terceros", json={"nombre": "Proveedor Uno", "tipo": "proveedor", "numero_documento": "2002"})).json()
    cab = ["Código de cuenta *", "Descripción", "Débito", "Crédito", "Documento del tercero (opcional)",
           "Número del documento (cartera)", "Fecha del documento (cartera)", "Vencimiento (cartera)"]
    sin_doc = [cab, ["1305", "Clientes", 800, None, "1001", None, None, None], ["3105", "Capital", None, 800, None, None, None, None]]
    r = await _importar(c, "saldos-iniciales", sin_doc, simular=False, fecha="2026-01-01")
    assert r.status_code == 422 and "número del documento" in r.json()["detail"]

    filas = [cab,
             ["1305", "Factura FV-10", 500, None, "1001", "FV-10", "2025-11-01", "2025-12-01"],
             ["1305", "Factura FV-11", 300, None, "1001", "FV-11", "2025-12-15", "2026-01-15"],
             ["2205", "Factura PR-7", None, 200, "2002", "PR-7", "2025-12-20", "2026-01-20"],
             ["3105", "Capital", None, 600, None, None, None, None]]
    r = await _importar(c, "saldos-iniciales", filas, simular=False, fecha="2026-01-01")
    assert r.status_code == 200 and r.json()["importado"], r.text

    cart = (await c.get("/api/tesoreria/cxc-cxp")).json()
    assert [d["documento"] for d in cart["cxc"]] == ["FV-10", "FV-11"] and cart["cxc"][0]["vencimiento"] == "2025-12-01"
    assert cart["cxp"][0]["documento"] == "PR-7" and cart["resumen"] == {"total_cxc": 800, "total_cxp": 200}
    ant = (await c.get("/api/tesoreria/cartera/antiguedad", params={"tipo": "cxc", "corte": "2026-01-31"})).json()
    assert ant["totales"]["d1_30"] == 300 and ant["totales"]["d61_90"] == 500

    # Se cobra una de ellas desde Tesorería y el libro cuadra con la cartera.
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    r = await c.post("/api/tesoreria/pagos", json={"documento_tipo": "cxc", "documento_id": cart["cxc"][0]["id"],
                                                    "cuenta_tipo": "caja", "cuenta_id": caja["id"], "fecha": "2026-02-01", "valor": 500})
    assert r.status_code == 201, r.text
    assert (await c.get("/api/tesoreria/cxc-cxp")).json()["resumen"]["total_cxc"] == 300
    est = (await c.get("/api/tesoreria/cartera/estado-cuenta", params={"tercero_id": cli["id"], "tipo": "cxc"})).json()
    assert est["resumen"] == {"facturado": 800, "pagado": 500, "saldo": 300}
    rep = (await c.get("/api/reportes/administrativos/cuentas-por-pagar", params=RANGO)).json()
    assert rep["resumen"]["saldo_total"] == 200

    # Con el saldo ya cobrado no se puede anular la apertura; al anular el cobro sí.
    ap = (await c.get("/api/contabilidad/comprobantes", params={"tipo": "apertura"})).json()[0]
    assert (await c.post(f"/api/contabilidad/comprobantes/{ap['id']}/anular", json={})).status_code == 409
    pago = (await c.get("/api/tesoreria/pagos")).json()[0]
    assert (await c.post(f"/api/tesoreria/pagos/{pago['id']}/anular", json={})).status_code == 200
    assert (await c.post(f"/api/contabilidad/comprobantes/{ap['id']}/anular", json={})).status_code == 200
    assert (await c.get("/api/tesoreria/cxc-cxp")).json()["resumen"] == {"total_cxc": 0, "total_cxp": 0}
