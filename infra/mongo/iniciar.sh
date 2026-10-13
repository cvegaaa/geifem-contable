#!/bin/bash
# Arranca mongod con replica set "rs0" + keyfile y lo inicializa la primera vez.
set -euo pipefail

: "${MONGO_INITDB_ROOT_USERNAME:?Falta MONGO_INITDB_ROOT_USERNAME}"
: "${MONGO_INITDB_ROOT_PASSWORD:?Falta MONGO_INITDB_ROOT_PASSWORD}"

KEYFILE=/data/configdb/keyfile
if [ ! -f "$KEYFILE" ]; then
  head -c 756 /dev/urandom | base64 -w 0 > "$KEYFILE"
fi
chmod 400 "$KEYFILE"
chown mongodb:mongodb "$KEYFILE"

# En segundo plano: espera a mongod e inicia el replica set si aún no existe.
# El miembro se registra como 127.0.0.1, por eso los clientes usan directConnection=true.
(
  until mongosh --quiet --host 127.0.0.1 \
      -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin \
      --eval "try { rs.status().ok } catch (e) { e.codeName === 'NotYetInitialized' ? rs.initiate({_id: 'rs0', members: [{_id: 0, host: '127.0.0.1:27017'}]}).ok : 0 }" \
      2>/dev/null | grep -q '^1$'; do
    sleep 3
  done
  echo "[geifem] replica set rs0 listo"
) &

exec docker-entrypoint.sh mongod --replSet rs0 --keyFile "$KEYFILE" --bind_ip_all
