# GEIFEM Contable — Backend (FastAPI)

## Requisitos
- Python 3.11+
- MongoDB Atlas (o Mongo local)

## Setup local
```bash
cd geifem-contable/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # editar valores
uvicorn main:app --reload --port 8000
```

## Inicializar índices
```bash
python ../database/init_indexes.py
```

## Estructura
- `api/` — routers por módulo funcional.
- `core/auth` — JWT, multi-tenant, roles y permisos por módulo.
- `core/puc` — semillas PUC por régimen (SIMPLE / Común).
- `core/dian` — contrato del Proveedor Tecnológico (Fase 1: interfaz).
- `core/retenciones` — placeholder Fase 2.
- `jobs/` — tareas programadas (alertas vencimientos).
