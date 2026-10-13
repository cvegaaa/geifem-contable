"""Fixtures de pruebas. Requieren el Mongo local (docker compose up -d mongo).

Usan una base aparte (`geifem_test`) que se borra antes de cada prueba.
"""
import os

os.environ["DB_NAME"] = "geifem_test"
os.environ["ENTORNO"] = "desarrollo"
os.environ["COOKIE_SECURE"] = "false"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from config import settings  # noqa: E402
from db import mongo  # noqa: E402
from db.indices import asegurar_indices  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def base_limpia():
    # Cada prueba corre en su propio event loop: se crea un cliente nuevo.
    await mongo.cerrar_cliente()
    await mongo.get_client().drop_database(settings.db_name)
    await asegurar_indices(mongo.get_db())
    yield
    await mongo.cerrar_cliente()


@pytest_asyncio.fixture
async def nuevo_cliente():
    """Fábrica de clientes HTTP; cada uno tiene su propio jar de cookies (sesión)."""
    clientes: list[AsyncClient] = []

    def _crear() -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clientes.append(c)
        return c

    yield _crear
    for c in clientes:
        await c.aclose()


async def registrar(c: AsyncClient, email: str, nit: str, razon_social: str = "Empresa SAS") -> dict:
    r = await c.post(
        "/api/auth/registro",
        json={
            "nombre": "Dueño",
            "email": email,
            "password": "clave-segura-1",
            "empresa": {"nit": nit, "razon_social": razon_social},
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    c.headers["X-Empresa-Id"] = data["empresa_activa_id"]
    return data
