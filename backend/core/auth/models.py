"""Modelos Pydantic para autenticación, usuarios y empresas."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Role = Literal["admin", "contador", "auxiliar", "vendedor"]
Regimen = Literal["ORDINARIO", "SIMPLE"]


def _validar_password(pw: str) -> str:
    # bcrypt solo usa los primeros 72 bytes; se rechaza en lugar de truncar.
    if len(pw.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return pw


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=120)
    rol: Role
    empresa_ids: list[str] = Field(default_factory=list)
    permisos: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapa modulo -> [acciones]. Ej: {'facturacion': ['leer','crear']}",
    )
    activo: bool = True
    # None = según el rol (el auxiliar requiere aprobación de lo que registra).
    requiere_aprobacion: bool | None = None


class UsuarioPublico(UsuarioBase):
    id: str


class UsuarioCrear(UsuarioBase):
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        return _validar_password(v)


class EmpresaDatos(BaseModel):
    nit: str = Field(pattern=r"^\d{5,15}$", description="NIT sin dígito de verificación")
    dv: str | None = Field(default=None, pattern=r"^\d$")
    razon_social: str = Field(min_length=2, max_length=200)
    regimen_tributario: Regimen = "ORDINARIO"
    # Independiente del régimen: un contribuyente SIMPLE también puede ser responsable de IVA.
    responsable_iva: bool = True
    ciudad: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    actividad_ciiu: str | None = Field(default=None, pattern=r"^\d{4}$")
    # Grupo de actividad del régimen SIMPLE (art. 908 ET): define las tarifas consolidadas.
    grupo_simple: int = Field(default=2, ge=1, le=5)

    # Perfil tributario (define qué impuestos y retenciones se pueden parametrizar).
    gran_contribuyente: bool = False
    # Agente de retención en la fuente (renta e ICA). Vacío = según el régimen.
    agente_retenedor: bool | None = None
    # Agente de retención de IVA. Vacío = según el régimen.
    agente_reteiva: bool | None = None
    autorretenedor_renta: bool = False
    tarifa_autorretencion: float = Field(default=0.8, ge=0, le=5, description="% sobre el ingreso")
    tarifa_reteica: float = Field(default=0, ge=0, le=30, description="Por mil (ICA del municipio)")

    @model_validator(mode="after")
    def _perfil_tributario(self):
        simple = self.regimen_tributario == "SIMPLE"
        if simple and self.agente_retenedor:
            raise ValueError(
                "Los contribuyentes del régimen SIMPLE no practican retención en la fuente (art. 911 ET), "
                "salvo pagos laborales y retención de IVA"
            )
        if simple and self.autorretenedor_renta:
            raise ValueError("Los contribuyentes del régimen SIMPLE no se autorretienen renta (art. 911 ET)")
        if self.agente_retenedor is None:
            self.agente_retenedor = not simple
        if self.agente_reteiva is None:
            self.agente_reteiva = not simple and self.responsable_iva
        if self.agente_reteiva and not self.responsable_iva:
            raise ValueError("Para retener IVA la empresa debe ser responsable de IVA")
        return self


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    empresa: EmpresaDatos

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        return _validar_password(v)


class CambioPassword(BaseModel):
    actual: str
    nueva: str = Field(min_length=8)

    @field_validator("nueva")
    @classmethod
    def validar_nueva(cls, v: str) -> str:
        return _validar_password(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SesionResponse(BaseModel):
    usuario: UsuarioPublico
    empresa_activa_id: str | None = None
