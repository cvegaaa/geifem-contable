"""Protección contra fuerza bruta: límite de intentos fallidos por correo y por dirección IP.

Los intentos se guardan en Mongo (`intentos_login`) con caducidad automática, de modo que el
límite sobrevive a reinicios y funciona con varias instancias del backend.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from config import settings
from db import get_db


def ip_cliente(request: Request) -> str:
    # Detrás de nginx y del proxy de Easypanel uvicorn ya resuelve la IP real (--proxy-headers).
    return request.client.host if request.client else "desconocida"


async def _contar(clave: str, ventana_min: int) -> int:
    desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_min)
    return await get_db().intentos_login.count_documents({"clave": clave, "fecha": {"$gte": desde}})


async def exigir_cupo(clave: str, maximo: int, ventana_min: int) -> None:
    """Rechaza con 429 si la clave ya agotó sus intentos en la ventana."""
    if await _contar(clave, ventana_min) >= maximo:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Espera {ventana_min} minutos antes de volver a intentar.",
            headers={"Retry-After": str(ventana_min * 60)},
        )


async def registrar_intento(clave: str) -> None:
    await get_db().intentos_login.insert_one({"clave": clave, "fecha": datetime.now(timezone.utc)})


async def limpiar(clave: str) -> None:
    await get_db().intentos_login.delete_many({"clave": clave})


async def exigir_cupo_login(email: str, ip: str) -> None:
    await exigir_cupo(f"login:{email.lower()}", settings.login_max_intentos, settings.login_ventana_min)
    await exigir_cupo(f"ip:{ip}", settings.login_max_intentos * 4, settings.login_ventana_min)


async def registrar_fallo_login(email: str, ip: str) -> None:
    await registrar_intento(f"login:{email.lower()}")
    await registrar_intento(f"ip:{ip}")


async def exigir_cupo_registro(ip: str) -> None:
    """Evita altas masivas desde una misma IP."""
    clave = f"registro:{ip}"
    await exigir_cupo(clave, settings.registro_max_por_hora, 60)
    await registrar_intento(clave)
