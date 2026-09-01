"""Entrada FastAPI de GEIFEM Contable."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.compras import router as compras_router
from api.configuracion import router as configuracion_router
from api.contabilidad import router as contabilidad_router
from api.facturacion import router as facturacion_router
from api.inventario import router as inventario_router
from api.reportes import router as reportes_router
from api.tesoreria import router as tesoreria_router
from config import settings
from core.auth import router as auth_router
from core.dian import webhooks_router

app = FastAPI(title="GEIFEM Contable API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "geifem-contable-api"}


app.include_router(auth_router)
app.include_router(configuracion_router)
app.include_router(contabilidad_router)
app.include_router(facturacion_router)
app.include_router(inventario_router)
app.include_router(reportes_router)
app.include_router(compras_router)
app.include_router(tesoreria_router)
app.include_router(webhooks_router)
