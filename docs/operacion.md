# Operación y despliegue

Guía para poner el sistema en un VPS con **Easypanel** y mantenerlo.

## 1. Antes de desplegar

- Un dominio (o subdominio) apuntando a la IP del VPS: por ejemplo `contable.tudominio.com`.
- Easypanel instalado en el VPS (instala Docker y Traefik; Traefik emite el certificado HTTPS).
- El repositorio en un remoto Git al que Easypanel pueda acceder (GitHub, GitLab…), o subir el código por la opción de Easypanel.
- Dos secretos generados en tu máquina, **guardados en un gestor de contraseñas**:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

  Uno para `JWT_SECRET` y otro (solo letras y números) para la clave de Mongo.

## 2. Servicios en Easypanel

Crea un proyecto `geifem` con cuatro servicios de tipo **App**, todos desde el mismo repositorio (compilación con Dockerfile, cambiando la ruta de compilación):

| Servicio   | Ruta de compilación | Dominio                      | Volúmenes                         |
|------------|---------------------|------------------------------|-----------------------------------|
| `mongo`    | `infra/mongo`       | ninguno                      | `/data/db` y `/data/configdb`     |
| `backend`  | `backend`           | ninguno                      | —                                 |
| `frontend` | `frontend`          | tu dominio → puerto 80, HTTPS | —                                |
| `respaldo` | `infra/respaldo`    | ninguno                      | `/respaldos`                      |

Variables de entorno:

- **mongo:** `MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD`.
- **backend:**
  - `ENTORNO=produccion`
  - `MONGO_URI=mongodb://USUARIO:CLAVE@geifem_mongo:27017/?authSource=admin&directConnection=true`
  - `DB_NAME=geifem_contable`
  - `JWT_SECRET=<el secreto generado>`
  - `COOKIE_SECURE=true`
  - `REGISTRO_ABIERTO=true` mientras creas las cuentas; luego `false` si no quieres altas públicas.
- **frontend:** `BACKEND_URL=http://geifem_backend:8000`
- **respaldo:** `MONGO_URI` (igual que el backend), `RESPALDO_HORA=03:00`, `RESPALDO_DIAS=14` y, **muy recomendado**, `RESPALDO_RCLONE` (ver §4).

Easypanel nombra los servicios internos como `<proyecto>_<servicio>`; confirma el nombre exacto en la pestaña de cada uno.

Orden de arranque: `mongo` → `backend` → `frontend` (y `respaldo`). El backend se niega a arrancar en producción si `JWT_SECRET` es débil o `COOKIE_SECURE` es `false`.

## 3. Primera puesta en marcha (lista de verificación)

1. Abre `https://tu-dominio`: debe cargar el login con candado.
2. Crea tu cuenta con **Crear cuenta** (con tu empresa).
3. Comprueba `https://tu-dominio/api/health` → `{"status":"ok"…}`.
4. Revisa en Easypanel los registros de `mongo`: debe decir `replica set rs0 listo`.
5. Ejecuta un respaldo de prueba (§4) y verifica que aparece el archivo.
6. Con `REGISTRO_ABIERTO=false`, intenta crear otra cuenta: debe responder que el registro está deshabilitado.
7. Anota la fecha del despliegue y la versión (hash del commit).

## 4. Respaldos

El servicio `respaldo` hace un volcado comprimido (`mongodump`) cada día a la hora configurada, conserva los últimos `RESPALDO_DIAS` días y registra cada ejecución en su consola.

**Un VPS no se respalda a sí mismo.** Configura una copia externa con `rclone`; por ejemplo, para un bucket S3 compatible (Backblaze B2, Wasabi, AWS…):

```
RESPALDO_RCLONE=remoto:mi-bucket/geifem
RCLONE_CONFIG_REMOTO_TYPE=s3
RCLONE_CONFIG_REMOTO_PROVIDER=Other
RCLONE_CONFIG_REMOTO_ACCESS_KEY_ID=...
RCLONE_CONFIG_REMOTO_SECRET_ACCESS_KEY=...
RCLONE_CONFIG_REMOTO_ENDPOINT=https://s3.us-west-000.backblazeb2.com
```

Respaldo manual inmediato (desde la consola del servicio `respaldo`):

```bash
RESPALDO_AHORA=1 /usr/local/bin/respaldar.sh
```

### Restaurar

1. Verifica el respaldo sin tocar producción: restáuralo en una base temporal:

   ```bash
   mongorestore --uri="$MONGO_URI" --archive=/respaldos/geifem-AAAAMMDD-HHMMSS.archivo.gz --gzip \
     --nsFrom='geifem_contable.*' --nsTo='geifem_verificacion.*'
   ```

2. Para restaurar de verdad (reemplaza las colecciones, **destructivo**):

   ```bash
   /usr/local/bin/restaurar.sh /respaldos/geifem-AAAAMMDD-HHMMSS.archivo.gz
   ```

**Haz una restauración de prueba al menos una vez al trimestre**: un respaldo que nunca se probó no es un respaldo.

### Correo saliente (envío de facturas)

Para «Enviar al cliente» el backend necesita un servidor SMTP (Gmail/Google Workspace con contraseña de aplicación, Microsoft 365, SendGrid, etc.).
Define en las variables del servicio `backend`: `SMTP_HOST`, `SMTP_PUERTO` (587 con STARTTLS o 465 con `SMTP_SSL=true`), `SMTP_USUARIO`,
`SMTP_PASSWORD` y `SMTP_REMITENTE`. Sin `SMTP_HOST` la aplicación responde que el correo no está configurado. El PDF se genera en el servidor;
el ZIP (PDF + XML) solo existe cuando la DIAN aceptó la factura.

## 5. Actualizar la aplicación

1. Despliega primero en una copia (o fuera de horario) y revisa que las pruebas del CI estén en verde.
2. Ejecuta un respaldo manual antes de actualizar.
3. En Easypanel, "Desplegar" `backend` y luego `frontend`. Los índices de Mongo se aplican solos al arrancar el backend.
4. Verifica `/api/health` y entra con tu usuario.

## 6. Seguridad: puntos a vigilar

- La contraseña de Mongo y el `JWT_SECRET` no se versionan ni se comparten; rotarlos invalida las sesiones.
- Mongo no se publica fuera de la red de Docker: no abras su puerto en el firewall del VPS.
- Mantén el sistema operativo del VPS y Easypanel actualizados.
- El inicio de sesión bloquea durante 15 minutos tras 5 intentos fallidos por cuenta (y por IP).
- Cambiar la contraseña cierra las demás sesiones abiertas.
