#!/bin/bash
# Restaura un respaldo sobre la base indicada. DESTRUCTIVO: reemplaza las colecciones.
#   restaurar.sh /respaldos/geifem-AAAAMMDD-HHMMSS.archivo.gz
set -euo pipefail
: "${MONGO_URI:?Falta MONGO_URI}"
archivo="${1:?Indica el archivo de respaldo}"
[ -f "$archivo" ] || { echo "No existe $archivo"; exit 1; }
echo "Se restaurará $archivo sobre la base actual (se reemplazan las colecciones)."
read -r -p "Escribe RESTAURAR para continuar: " c
[ "$c" = "RESTAURAR" ] || { echo "Cancelado"; exit 1; }
mongorestore --uri="$MONGO_URI" --archive="$archivo" --gzip --drop
