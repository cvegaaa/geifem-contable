from config import settings
from tests.conftest import registrar


async def test_registro_crea_empresa_con_puc_y_bodega(nuevo_cliente):
    c = nuevo_cliente()
    data = await registrar(c, "dueno@a.co", "900111222")

    assert data["usuario"]["rol"] == "admin"
    assert "password_hash" not in data["usuario"]
    assert settings.cookie_nombre in c.cookies

    me = await c.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["empresa_ids"] == [data["empresa_activa_id"]]

    empresas = (await c.get("/api/configuracion/datos-empresa")).json()
    assert [e["nit"] for e in empresas] == ["900111222"]

    codigos = {cta["codigo"] for cta in (await c.get("/api/configuracion/plan-cuentas")).json()}
    # Las cuentas que usan los asientos automáticos deben existir desde el inicio.
    assert {"1105", "1110", "1305", "1435", "2205", "2365", "2367", "2368", "2408",
            "4135", "6135", "6205"} <= codigos

    bodegas = (await c.get("/api/inventario/bodegas")).json()
    assert [b["nombre"] for b in bodegas] == ["Principal"]


async def test_registro_rechaza_duplicados_sin_dejar_huerfanos(nuevo_cliente):
    await registrar(nuevo_cliente(), "uno@a.co", "900111222")
    c = nuevo_cliente()

    r = await c.post("/api/auth/registro", json={
        "nombre": "X", "email": "uno@a.co", "password": "clave-segura-1",
        "empresa": {"nit": "800000001", "razon_social": "Otra"}})
    assert r.status_code == 409

    r = await c.post("/api/auth/registro", json={
        "nombre": "X", "email": "dos@a.co", "password": "clave-segura-1",
        "empresa": {"nit": "900111222", "razon_social": "Otra"}})
    assert r.status_code == 409
    # El usuario del intento fallido no debe haber quedado creado.
    login = await c.post("/api/auth/login", json={"email": "dos@a.co", "password": "clave-segura-1"})
    assert login.status_code == 401


async def test_registro_valida_datos(nuevo_cliente):
    c = nuevo_cliente()
    base = {"nombre": "X", "email": "x@a.co", "empresa": {"nit": "900111222", "razon_social": "E SAS"}}
    assert (await c.post("/api/auth/registro", json={**base, "password": "corta"})).status_code == 422
    malo = {**base, "password": "clave-segura-1", "empresa": {"nit": "90-11", "razon_social": "E SAS"}}
    assert (await c.post("/api/auth/registro", json=malo)).status_code == 422


async def test_registro_deshabilitado(nuevo_cliente, monkeypatch):
    monkeypatch.setattr(settings, "registro_abierto", False)
    r = await nuevo_cliente().post("/api/auth/registro", json={
        "nombre": "X", "email": "x@a.co", "password": "clave-segura-1",
        "empresa": {"nit": "900111222", "razon_social": "E SAS"}})
    assert r.status_code == 403


async def test_login_logout(nuevo_cliente):
    await registrar(nuevo_cliente(), "dueno@a.co", "900111222")
    c = nuevo_cliente()

    malo = await c.post("/api/auth/login", json={"email": "dueno@a.co", "password": "incorrecta"})
    assert malo.status_code == 401

    ok = await c.post("/api/auth/login", json={"email": "dueno@a.co", "password": "clave-segura-1"})
    assert ok.status_code == 200
    assert "access_token" not in ok.json()  # el token solo viaja en la cookie httpOnly
    assert (await c.get("/api/auth/me")).status_code == 200

    assert (await c.post("/api/auth/logout")).status_code == 204
    assert (await c.get("/api/auth/me")).status_code == 401


async def test_sin_sesion_no_hay_acceso(nuevo_cliente):
    c = nuevo_cliente()
    assert (await c.get("/api/configuracion/terceros")).status_code == 401
    assert (await c.get("/api/configuracion/datos-empresa")).status_code == 401


async def test_bloqueo_por_intentos_fallidos(nuevo_cliente):
    await registrar(nuevo_cliente(), "dueno@a.co", "900111222")
    c = nuevo_cliente()
    mala = {"email": "dueno@a.co", "password": "incorrecta-1"}
    for _ in range(settings.login_max_intentos):
        assert (await c.post("/api/auth/login", json=mala)).status_code == 401
    # Agotados los intentos, ni la clave correcta entra hasta que pase la ventana.
    r = await c.post("/api/auth/login", json={"email": "dueno@a.co", "password": "clave-segura-1"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    # El límite es por cuenta: otra cuenta no se ve afectada.
    r = await c.post("/api/auth/login", json={"email": "otro@a.co", "password": "x-clave-123"})
    assert r.status_code == 401


async def test_login_exitoso_reinicia_el_contador(nuevo_cliente):
    await registrar(nuevo_cliente(), "dueno@a.co", "900111222")
    c = nuevo_cliente()
    mala = {"email": "dueno@a.co", "password": "incorrecta-1"}
    for _ in range(settings.login_max_intentos - 1):
        await c.post("/api/auth/login", json=mala)
    assert (await c.post("/api/auth/login", json={"email": "dueno@a.co", "password": "clave-segura-1"})).status_code == 200
    for _ in range(settings.login_max_intentos - 1):
        assert (await c.post("/api/auth/login", json=mala)).status_code == 401


async def test_limite_de_altas_por_ip(nuevo_cliente):
    await registrar(nuevo_cliente(), "dueno@a.co", "900111222")
    c = nuevo_cliente()
    cuerpo = {"nombre": "X", "email": "dueno@a.co", "password": "clave-segura-1",
              "empresa": {"nit": "800000001", "razon_social": "Otra SAS"}}
    estados = [(await c.post("/api/auth/registro", json=cuerpo)).status_code for _ in range(settings.registro_max_por_hora)]
    assert estados[-1] == 429


async def test_cambiar_password_cierra_otras_sesiones(nuevo_cliente):
    a = nuevo_cliente()
    await registrar(a, "dueno@a.co", "900111222")
    b = nuevo_cliente()
    await b.post("/api/auth/login", json={"email": "dueno@a.co", "password": "clave-segura-1"})
    assert (await b.get("/api/auth/me")).status_code == 200

    r = await a.post("/api/auth/cambiar-password", json={"actual": "equivocada-1", "nueva": "otra-clave-9"})
    assert r.status_code == 400
    r = await a.post("/api/auth/cambiar-password", json={"actual": "clave-segura-1", "nueva": "otra-clave-9"})
    assert r.status_code == 204
    assert (await a.get("/api/auth/me")).status_code == 200      # la sesión actual se renueva
    assert (await b.get("/api/auth/me")).status_code == 401      # las demás se cierran
    ok = await nuevo_cliente().post("/api/auth/login", json={"email": "dueno@a.co", "password": "otra-clave-9"})
    assert ok.status_code == 200
