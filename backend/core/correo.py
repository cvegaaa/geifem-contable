"""Envío de correo saliente (SMTP) para entregar documentos a clientes y terceros."""
import asyncio
import smtplib
from email.message import EmailMessage

from config import settings


class CorreoNoConfigurado(RuntimeError):
    pass


def _enviar_sync(destinatarios: list[str], asunto: str, cuerpo: str, adjuntos: list[tuple[str, bytes, str]]) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_remitente or settings.smtp_usuario
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    for nombre, contenido, mime in adjuntos:
        tipo, _, subtipo = mime.partition("/")
        msg.add_attachment(contenido, maintype=tipo, subtype=subtipo, filename=nombre)
    clase = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
    with clase(settings.smtp_host, settings.smtp_puerto, timeout=30) as servidor:
        if not settings.smtp_ssl and settings.smtp_starttls:
            servidor.starttls()
        if settings.smtp_usuario:
            servidor.login(settings.smtp_usuario, settings.smtp_password)
        servidor.send_message(msg)


async def enviar(destinatarios: list[str], asunto: str, cuerpo: str, adjuntos: list[tuple[str, bytes, str]] | None = None) -> None:
    """Envía un correo con adjuntos [(nombre, contenido, tipo_mime)]. Lanza `CorreoNoConfigurado` si falta el servidor SMTP."""
    if not settings.smtp_host:
        raise CorreoNoConfigurado(
            "El envío de correo no está configurado en el servidor: define SMTP_HOST, SMTP_PUERTO, SMTP_USUARIO, "
            "SMTP_PASSWORD y SMTP_REMITENTE (ver docs/operacion.md).")
    await asyncio.to_thread(_enviar_sync, destinatarios, asunto, cuerpo, adjuntos or [])
