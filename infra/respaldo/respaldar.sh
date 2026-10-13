#!/bin/bash
# Respaldo diario de MongoDB.
#
# Variables:
#   MONGO_URI            conexión (obligatoria), con usuario y authSource
#   RESPALDO_HORA        hora local de ejecución, HH:MM (por defecto 03:00)
#   TZ                   zona horaria (por defecto America/Bogota)
#   RESPALDO_DIAS        cuántos días conservar (por defecto 14)
#   RESPALDO_AHORA=1     ejecuta un respaldo ya y termina (para pruebas)
#   RESPALDO_RCLONE      destino externo opcional de rclone, p. ej. "s3remoto:mi-bucket/geifem"
#                        (la configuración se pasa con variables RCLONE_CONFIG_<REMOTO>_*)
set -euo pipefail

: "${MONGO_URI:?Falta MONGO_URI}"
export TZ="${TZ:-America/Bogota}"
HORA="${RESPALDO_HORA:-03:00}"
DIAS="${RESPALDO_DIAS:-14}"
DESTINO=/respaldos

respaldar() {
  local archivo="$DESTINO/geifem-$(date +%Y%m%d-%H%M%S).archivo.gz"
  echo "[respaldo] $(date -Is) iniciando -> $archivo"
  mongodump --uri="$MONGO_URI" --archive="$archivo.tmp" --gzip --quiet
  mv "$archivo.tmp" "$archivo"
  echo "[respaldo] listo ($(du -h "$archivo" | cut -f1))"

  # Rotación local
  find "$DESTINO" -name 'geifem-*.archivo.gz' -mtime +"$DIAS" -delete

  # Copia fuera del servidor (recomendado: un VPS no se respalda a sí mismo)
  if [ -n "${RESPALDO_RCLONE:-}" ]; then
    rclone copy "$archivo" "$RESPALDO_RCLONE" && echo "[respaldo] copiado a $RESPALDO_RCLONE" \
      || echo "[respaldo] ERROR copiando a $RESPALDO_RCLONE" >&2
  fi
}

if [ "${RESPALDO_AHORA:-0}" = "1" ]; then
  respaldar
  exit 0
fi

echo "[respaldo] programado a las $HORA ($TZ), conserva $DIAS días"
while true; do
  ahora=$(date +%s)
  objetivo=$(date -d "today $HORA" +%s)
  [ "$objetivo" -le "$ahora" ] && objetivo=$(date -d "tomorrow $HORA" +%s)
  sleep $((objetivo - ahora))
  respaldar || echo "[respaldo] ERROR en el respaldo" >&2
done
