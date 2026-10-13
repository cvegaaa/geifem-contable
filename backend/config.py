"""Configuración global leída desde variables de entorno."""
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETO_POR_DEFECTO = "solo-para-desarrollo-local-no-usar-en-produccion"


class Settings(BaseSettings):
    entorno: Literal["desarrollo", "produccion"] = "desarrollo"

    mongo_uri: str = "mongodb://localhost:27017/?directConnection=true"
    db_name: str = "geifem_contable"

    jwt_secret: str = SECRETO_POR_DEFECTO
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # La sesión viaja en una cookie httpOnly; en producción exige HTTPS.
    cookie_nombre: str = "geifem_sesion"
    cookie_secure: bool = False

    # Solo necesario si el frontend se sirve desde otro origen. Con el proxy
    # de nginx (producción) o de Vite (desarrollo) todo es mismo origen.
    cors_origins: str = ""

    # Permite que cualquier persona cree cuenta + empresa desde el login.
    registro_abierto: bool = True

    # Protección contra fuerza bruta.
    login_max_intentos: int = 5
    login_ventana_min: int = 15
    registro_max_por_hora: int = 5

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def _validar_produccion(self):
        if self.entorno == "produccion":
            if self.jwt_secret == SECRETO_POR_DEFECTO or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET debe tener al menos 32 caracteres en producción")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE debe ser true en producción (HTTPS)")
        return self


settings = Settings()
