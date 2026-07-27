# GEIFEM Contable

Sistema contable SaaS multi-tenant para pequeños comerciantes colombianos.
Soporta régimen SIMPLE y Común, costeo de inventario por Promedio Ponderado,
y canales POS + online.

> **Estado**: FASE 1 macro (andamiaje). Facturación electrónica DIAN queda
> con contrato preparado pero sin credenciales del Proveedor Tecnológico.

## Stack
- **Frontend**: React + Vite + Tailwind CSS (`geifem-contable/frontend/`).
- **Backend**: FastAPI + Motor (`geifem-contable/backend/`).
- **Base de datos**: MongoDB Atlas (`geifem-contable/database/`).

## Correr localmente

### 1) Backend
```bash
cd geifem-contable/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # editar MONGO_URI, JWT_SECRET, etc.
uvicorn main:app --reload --port 8000
```

### 2) Índices Mongo (primera vez)
```bash
cd geifem-contable/database
python init_indexes.py
```

### 3) Frontend
```bash
cd geifem-contable/frontend
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install    # o: bun install
npm run dev    # http://localhost:5173
```

### 4) Registro inicial (temporal, Fase 1)
```bash
curl -X POST http://localhost:8000/api/auth/registro \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@geifem.co","password":"changeme","nombre":"Admin","rol":"admin"}'
```

## Estructura
```
geifem-contable/
├── frontend/     (React + Vite)
├── backend/      (FastAPI)
├── database/     (índices y esquema)
└── docs/         (cumplimiento DIAN, integración PT)
```

## Roles y permisos
Roles base: `admin`, `contador`, `vendedor`. Cada rol trae una plantilla de
permisos por módulo (`configuracion`, `contabilidad`, `facturacion`,
`inventario`, `reportes`, `compras`, `tesoreria`) con acciones
(`leer`, `crear`, `editar`, `inactivar`). Los permisos se personalizan por
usuario dentro del rol desde `configuracion/usuarios-roles`.

## Multi-tenant
Cada comerciante = 1 empresa. Todas las operaciones requieren el header
`X-Empresa-Id` (el frontend lo envía automáticamente al elegir empresa en el
selector superior).

## Despliegue
El despliegue se realiza de forma independiente: frontend en Vercel, backend
en Railway, base de datos en MongoDB Atlas. Este repositorio no incluye
configuración de CI/CD.

## Fases
- **Fase 1** (actual, andamiaje): configuración, contabilidad, facturación
  base, inventario PP, reportes básicos.
- **Fase 2**: compras + tesorería + retenciones + Form-350 + libros oficiales.
- **Fase 3**: conciliación bancaria automática + exógena + calendario
  tributario + reglas por empresa.
