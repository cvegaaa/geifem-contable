"""Entrada FastAPI de GEIFEM Contable."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.archivos import router as archivos_router
from api.compras import router as compras_router
from api.configuracion import router as configuracion_router
from api.contabilidad import router as contabilidad_router
from api.facturacion import router as facturacion_router
from api.inventario import router as inventario_router
from api.nomina import router as nomina_router
from api.reportes import router as reportes_router
from api.tesoreria import router as tesoreria_router
from config import settings
from core.auth import router as auth_router
from db import cerrar_cliente, get_db
from db.indices import asegurar_indices


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asegurar_indices(get_db())
    yield
    await cerrar_cliente()


app = FastAPI(
    title="GEIFEM Contable API",
    version="0.1.0",
    lifespan=lifespan,
    # La documentación interactiva solo se expone en desarrollo.
    docs_url="/api/docs" if settings.entorno == "desarrollo" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.entorno == "desarrollo" else None,
)

origenes = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origenes:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health")
async def health():
    await get_db().command("ping")
    return {"status": "ok", "service": "geifem-contable-api"}


app.include_router(auth_router)
app.include_router(configuracion_router)
app.include_router(contabilidad_router)
app.include_router(facturacion_router)
app.include_router(inventario_router)
app.include_router(reportes_router)
app.include_router(compras_router)
app.include_router(tesoreria_router)
app.include_router(nomina_router)
app.include_router(archivos_router)
