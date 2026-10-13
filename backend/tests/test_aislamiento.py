"""Ningún usuario, ni siquiera un admin, puede ver o tocar datos de otra empresa."""
from tests.conftest import registrar


async def _dos_empresas(nuevo_cliente):
    a, b = nuevo_cliente(), nuevo_cliente()
    da = await registrar(a, "a@a.co", "900000001", "Empresa A")
    db_ = await registrar(b, "b@b.co", "900000002", "Empresa B")
    return a, b, da["empresa_activa_id"], db_["empresa_activa_id"]


async def test_admin_no_accede_a_empresa_ajena(nuevo_cliente):
    a, b, emp_a, emp_b = await _dos_empresas(nuevo_cliente)

    r = await b.get("/api/configuracion/terceros", headers={"X-Empresa-Id": emp_a})
    assert r.status_code == 403
    assert (await b.get(f"/api/configuracion/datos-empresa/{emp_a}")).status_code == 404
    empresas_b = (await b.get("/api/configuracion/datos-empresa")).json()
    assert [e["id"] for e in empresas_b] == [emp_b]


async def test_datos_quedan_en_su_empresa(nuevo_cliente):
    a, b, emp_a, emp_b = await _dos_empresas(nuevo_cliente)

    # Aunque el cuerpo traiga otro empresa_id, se guarda en la empresa activa.
    r = await b.post("/api/configuracion/terceros", json={
        "nombre": "Cliente de B", "numero_documento": "123", "empresa_id": emp_a})
    assert r.status_code == 201
    assert r.json()["empresa_id"] == emp_b

    assert (await a.get("/api/configuracion/terceros")).json() == []


async def test_usuarios_y_auditoria_aislados(nuevo_cliente):
    a, b, emp_a, emp_b = await _dos_empresas(nuevo_cliente)

    r = await a.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Vendedor A", "email": "vend@a.co", "password": "clave-segura-1", "rol": "vendedor"})
    assert r.status_code == 201
    assert r.json()["empresa_ids"] == [emp_a]

    emails_b = {u["email"] for u in (await b.get("/api/configuracion/usuarios-roles")).json()}
    assert emails_b == {"b@b.co"}

    # Comprobante en A: su auditoría no debe verse desde B.
    cuentas = {c["codigo"]: c["id"] for c in (await a.get("/api/configuracion/plan-cuentas")).json()}
    r = await a.post("/api/contabilidad/comprobantes", json={
        "tipo": "ajuste", "fecha": "2026-10-01",
        "lineas": [
            {"cuenta_puc_id": cuentas["1105"], "debito": 1000},
            {"cuenta_puc_id": cuentas["3105"], "credito": 1000},
        ]})
    assert r.status_code == 201, r.text
    assert len((await a.get("/api/contabilidad/auditoria")).json()) == 1
    assert (await b.get("/api/contabilidad/auditoria")).json() == []


async def test_gestion_de_usuarios_restringida(nuevo_cliente):
    a, b, emp_a, emp_b = await _dos_empresas(nuevo_cliente)

    # Un admin no puede asignar empresas a las que no pertenece.
    r = await a.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Intruso", "email": "i@a.co", "password": "clave-segura-1",
        "rol": "admin", "empresa_ids": [emp_b]})
    assert r.status_code == 403

    # Un no-admin no puede crear usuarios (evita escalar privilegios).
    r = await a.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Contador", "email": "cont@a.co", "password": "clave-segura-1", "rol": "contador"})
    assert r.status_code == 201
    cont = nuevo_cliente()
    await cont.post("/api/auth/login", json={"email": "cont@a.co", "password": "clave-segura-1"})
    cont.headers["X-Empresa-Id"] = emp_a
    r = await cont.post("/api/configuracion/usuarios-roles", json={
        "nombre": "Nuevo admin", "email": "n@a.co", "password": "clave-segura-1", "rol": "admin"})
    assert r.status_code == 403


async def test_admin_crea_segunda_empresa(nuevo_cliente):
    a = nuevo_cliente()
    await registrar(a, "a@a.co", "900000001")

    r = await a.post("/api/configuracion/datos-empresa", json={"nit": "900000009", "razon_social": "Sucursal"})
    assert r.status_code == 201
    nueva = r.json()["id"]

    assert nueva in (await a.get("/api/auth/me")).json()["empresa_ids"]
    bodegas = await a.get("/api/inventario/bodegas", headers={"X-Empresa-Id": nueva})
    assert [x["nombre"] for x in bodegas.json()] == ["Principal"]
