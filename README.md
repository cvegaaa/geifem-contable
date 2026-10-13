# GEIFEM Contable

Sistema contable SaaS multiempresa para comerciantes colombianos (régimen
ordinario y SIMPLE), con inventario por promedio ponderado y facturación
electrónica DIAN a través de **Alegra**.

> **Estado:** pre-alfa, en **Fase 0** (que corra y sea seguro). No usar con datos
> reales todavía. El avance por etapas está en [ROADMAP.md](ROADMAP.md).

## Arquitectura

```
                Internet (HTTPS)
                       │
          Easypanel (Traefik, certificados)
                       │
              ┌────────▼────────┐
              │    frontend     │  nginx: sirve el SPA (React)
              │  (puerto 80)    │  y reenvía /api/* al backend
              └────────┬────────┘
                       │ red interna
              ┌────────▼────────┐
              │     backend     │  FastAPI (Python 3.14)
              │  (puerto 8000)  │
              └────────┬────────┘
                       │ red interna
              ┌────────▼────────┐
              │      mongo      │  MongoDB 8, replica set "rs0"
              │ (puerto 27017)  │  con autenticación (transacciones)
              └─────────────────┘
```

- **Mismo origen:** el navegador solo habla con el frontend; nginx reenvía `/api`.
  Así la sesión viaja en una cookie `httpOnly` sin configurar CORS.
- **Multiempresa:** cada petición de datos lleva el encabezado `X-Empresa-Id` y el
  backend verifica que el usuario pertenezca a esa empresa (sin excepciones para admin).
- **MongoDB en replica set** de un nodo: necesario para las transacciones que
  garantizan que factura, consecutivo y asiento se graben juntos o no se graben.
- **Solo el frontend se publica.** Backend y Mongo quedan en la red interna.

## Estructura

```
backend/        API FastAPI (api/ por módulo, core/ auth-empresas-PUC-DIAN, db/, tests/)
frontend/       SPA React + Vite + Tailwind; nginx/ con la configuración de producción
infra/mongo/    Imagen de MongoDB con replica set + autenticación autoconfigurados
infra/respaldo/ Respaldo diario de Mongo con rotación y copia externa opcional
docs/           Modelo de datos y guía de operación
docker-compose.yml  Stack completo (local y referencia para el VPS)
ROADMAP.md      Ruta de trabajo por etapas (se actualiza con cada avance)
```

## Desarrollo local

Requisitos: Docker Desktop, Python 3.14, Node 24.

```bash
cp .env.example .env
```

```bash
docker compose up -d mongo
```

Backend (en `backend/`):

```bash
py -3.14 -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

```bash
cp .env.example .env
```

```bash
.venv/Scripts/python -m uvicorn main:app --reload --port 8000
```

La clave de `MONGO_URI` en `backend/.env` debe coincidir con `MONGO_PASSWORD` del
`.env` raíz. La documentación de la API queda en http://localhost:8000/api/docs.

Frontend (en `frontend/`):

```bash
npm install
```

```bash
npm run dev
```

Abre http://localhost:5173, elige **Crear cuenta** y registra tu usuario junto con
tu empresa (se crea con el plan de cuentas base y la bodega principal).

### Pruebas

Con el Mongo local arriba, desde `backend/`:

```bash
.venv/Scripts/python -m pytest
```

Usan una base aparte (`geifem_test`) que se borra en cada prueba.

### Todo el stack en Docker (como en producción)

```bash
docker compose up -d --build
```

Abre http://localhost:8080.

## Despliegue en el VPS (Easypanel)

La guía completa (servicios, variables, lista de verificación, respaldos y restauración) está en
[docs/operacion.md](docs/operacion.md). En resumen: cuatro servicios desde este repositorio
(`mongo`, `backend`, `frontend` y `respaldo`); solo `frontend` se publica, con HTTPS de Traefik.

## Seguridad (resumen)

- Contraseñas con bcrypt; sesión JWT en cookie `httpOnly`, `SameSite=Lax`, `Secure` en producción.
- Aislamiento por empresa verificado por pruebas automatizadas (`backend/tests/test_aislamiento.py`).
- Solo un admin gestiona usuarios y solo puede asignar empresas a las que pertenece.
- La documentación interactiva de la API se desactiva en producción.
- Nunca versionar `.env`: solo los `.env.example`.
