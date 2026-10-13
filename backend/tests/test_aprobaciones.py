"""Aprobación de documentos de todos los módulos: la petición queda como solicitud y se ejecuta al aprobarla."""
from tests.test_archivos_usuarios import _con_usuario
from tests.test_documentos import FECHA, _empresa, _existencia, _preparar_ventas


async def _facturador(c, nuevo_cliente, aprobacion=True):
    r = await c.post("/api/configuracion/roles", json={
        "nombre": "Facturador", "requiere_aprobacion": aprobacion,
        "permisos": {"facturacion": ["leer", "crear", "editar", "inactivar"], "tesoreria": ["leer", "crear"],
                     "configuracion": ["leer"], "inventario": ["leer"], "contabilidad": ["leer"]}})
    assert r.status_code == 201, r.text
    return await _con_usuario(c, nuevo_cliente, "fac@a.co", "facturador")


async def test_solicitud_de_factura_se_aprueba_y_se_ejecuta_a_nombre_del_solicitante(nuevo_cliente):
    c, _ = await _empresa(nuevo_cliente)
    prod, cliente, _, resol, bodega = await _preparar_ventas(c)
    await c.post("/api/compras/recepcion-mercancia", json={
        "bodega_id": bodega["id"], "fecha": FECHA, "items": [{"producto_id": prod["id"], "cantidad": 10, "costo_unitario": 100}]})
    u, fac = await _facturador(c, nuevo_cliente)
    cuerpo = {"cliente_id": cliente["id"], "resolucion_id": resol["id"], "fecha": FECHA,
              "items": [{"producto_id": prod["id"], "cantidad": 2, "precio_unitario": 500}]}

    r = await fac.post("/api/facturacion/facturas", json=cuerpo)
    assert r.status_code == 202 and r.json()["por_aprobar"] and "Pendiente de aprobación" in r.json()["detail"]
    assert (await c.get("/api/facturacion/facturas")).json() == []                  # aún no existe
    assert await _existencia(c, prod["id"]) == 10

    # El solicitante ve su solicitud pero no la puede resolver; el administrador sí.
    mias = (await fac.get("/api/aprobaciones")).json()
    assert len(mias) == 1 and mias[0]["propio"] and not mias[0]["puede_resolver"] and mias[0]["modulo"] == "facturacion"
    assert (await fac.post(f"/api/aprobaciones/{mias[0]['id']}/aprobar")).status_code == 403
    assert (await c.get("/api/aprobaciones/contar")).json() == {"pendientes": 1}
    pend = (await c.get("/api/aprobaciones")).json()
    assert pend[0]["puede_resolver"] and pend[0]["usuario_nombre"] == "Usuario" and pend[0]["descripcion"] == "Crear: Factura de venta"

    r = await c.post(f"/api/aprobaciones/{pend[0]['id']}/aprobar")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobada" and r.json()["resultado"]["numero"] == "FE1" and r.json()["aprobado_por"] == "Dueño"
    facturas = (await c.get("/api/facturacion/facturas")).json()
    assert len(facturas) == 1 and facturas[0]["creado_por"] == u["id"]               # a nombre de quien la pidió
    assert await _existencia(c, prod["id"]) == 8
    assert (await c.post(f"/api/aprobaciones/{pend[0]['id']}/aprobar")).status_code == 409
    firmas = (await c.get(f"/api/contabilidad/firmas/{facturas[0]['id']}")).json()
    assert firmas == {"elaboro": "Usuario", "aprobo": "Dueño"}
    assert (await c.get("/api/aprobaciones/contar")).json() == {"pendientes": 0}

    # También se aprueba anular: queda pendiente hasta que el administrador lo autorice.
    r = await fac.post(f"/api/facturacion/facturas/{facturas[0]['id']}/anular", json={"motivo": "Error"})
    assert r.status_code == 202
    assert (await c.get(f"/api/facturacion/facturas/{facturas[0]['id']}")).json()["estado"] != "anulado"
    sol = (await c.get("/api/aprobaciones")).json()[0]
    assert (await c.post(f"/api/aprobaciones/{sol['id']}/aprobar")).status_code == 200
    assert (await c.get(f"/api/facturacion/facturas/{facturas[0]['id']}")).json()["estado"] == "anulado"


async def test_rechazo_cancelacion_y_errores_al_ejecutar(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    _, fac = await _facturador(c, nuevo_cliente)
    caja = (await c.post("/api/tesoreria/cuentas-caja", json={"nombre": "Caja"})).json()
    mov = {"cuenta_tipo": "caja", "cuenta_id": caja["id"], "tipo": "ingreso", "fecha": FECHA, "valor": 100,
           "concepto": "Fondeo", "cuenta_contrapartida": "3105"}

    assert (await fac.post("/api/tesoreria/movimientos", json=mov)).status_code == 202
    sol = (await c.get("/api/aprobaciones")).json()[0]
    assert sol["resumen"]["valor"] == 100 and sol["resumen"]["concepto"] == "Fondeo"
    assert (await c.post(f"/api/aprobaciones/{sol['id']}/rechazar", json={"motivo": "ab"})).status_code == 422
    r = await c.post(f"/api/aprobaciones/{sol['id']}/rechazar", json={"motivo": "No está soportado"})
    assert r.json()["estado"] == "rechazada" and r.json()["motivo_rechazo"] == "No está soportado"
    assert (await c.get("/api/tesoreria/movimientos")).json() == []
    visto = (await fac.get("/api/aprobaciones", params={"estado": "todas"})).json()[0]
    assert visto["estado"] == "rechazada" and visto["motivo_rechazo"]

    # El solicitante puede retirar la suya; si al aprobar falla (cuenta inexistente), sigue pendiente con el error.
    assert (await fac.post("/api/tesoreria/movimientos", json=mov)).status_code == 202
    retirada = (await fac.get("/api/aprobaciones")).json()[0]
    assert (await fac.post(f"/api/aprobaciones/{retirada['id']}/cancelar")).json()["estado"] == "cancelada"
    assert (await fac.post("/api/tesoreria/movimientos", json={**mov, "cuenta_contrapartida": "9999"})).status_code == 202
    mala = (await c.get("/api/aprobaciones")).json()[0]
    r = await c.post(f"/api/aprobaciones/{mala['id']}/aprobar")
    assert r.status_code == 409 and "No se pudo registrar" in r.json()["detail"]
    assert (await c.get("/api/aprobaciones")).json()[0]["ultimo_error"]

    # Sin permiso sigue siendo 403 (no se guarda solicitud) y quien no requiere aprobación opera directo.
    assert (await fac.post("/api/nomina/periodos", json={})).status_code == 403
    assert (await c.post("/api/tesoreria/movimientos", json=mov)).status_code == 201


async def test_comprobantes_y_solicitudes_se_listan_juntos(nuevo_cliente):
    c, cuentas = await _empresa(nuevo_cliente)
    _, aux = await _con_usuario(c, nuevo_cliente, "aux@a.co", "auxiliar")
    r = await aux.post("/api/contabilidad/comprobantes", json={
        "tipo": "ajuste", "fecha": FECHA, "estado": "contabilizado",
        "lineas": [{"cuenta_puc_id": cuentas["1105"], "debito": 10}, {"cuenta_puc_id": cuentas["3105"], "credito": 10}]})
    assert r.json()["estado"] == "por_aprobar"
    lista = (await c.get("/api/aprobaciones")).json()
    assert [i["tipo"] for i in lista] == ["comprobante"] and lista[0]["puede_resolver"] and lista[0]["modulo"] == "contabilidad"
    assert (await c.get("/api/aprobaciones/contar")).json() == {"pendientes": 1}
